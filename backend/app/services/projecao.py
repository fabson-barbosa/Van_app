"""Projeção da cauda + atraso acumulado (Bloco B3, CLAUDE.md §5).

Lógica pura — mesma filosofia de `trip_state_machine.py`/`leg_duration.py`:
recebe dados já resolvidos (timestamps, previsões por trecho), devolve o que
calcular; quem busca no banco e persiste é `app/services/pos_evento.py`.

Dois números coexistem e têm papéis DELIBERADAMENTE diferentes — decisão
tomada com o usuário, não são intercambiáveis nem se somam:

- `atraso_acumulado_segundos` (`calcular_atraso_acumulado`): só
  diagnóstico/exibição para o gestor. `chegou_em(parada atual) - iniciada_em
  - previsto acumulado até essa parada`. Recalculado do zero a cada Cheguei
  (substitui, não acumula). NÃO entra em `projetar_cauda`.
  Simplificação assumida (documentar se questionada): "previsto" usa os
  `leg_durations` de AGORA, não um snapshot congelado no instante exato em
  que a viagem começou — como este número é só para exibição (não dirige
  agendamento de notificação nem SLA), a small deriva ao longo da viagem é
  aceitável; uma versão com snapshot exigiria uma coluna nova por
  trip_student, fora do que foi aprovado nesta rodada.
- `atraso_manual_segundos` (`Viagem`, fora deste módulo): acumulado do botão
  "Estou atrasado". Este SIM entra em `projetar_cauda` — é a única forma de
  empurrar a cauda antes do próximo evento real acontecer.

`projetar_cauda` ancora no ÚLTIMO EVENTO REAL (não soma `atraso_acumulado_segundos`
por cima): o timestamp real de onde a viagem está agora já embute qualquer
atraso ocorrido até aqui. Somar `atraso_acumulado_segundos` de novo contaria
o mesmo atraso duas vezes.
"""
from __future__ import annotations

import datetime
import uuid
from collections.abc import Mapping, Sequence


def previsao_acumulada_ate(
    ordens_ordenadas: Sequence[int], previsao_por_ordem: Mapping[int, float]
) -> dict[int, float]:
    """Soma cumulativa dos trajetos previstos, do início da viagem até cada parada.

    `previsao_por_ordem[ordem]` é o trajeto previsto (segundos) que TERMINA
    nessa parada — mesma convenção de `LegDuration.ordem`/`leg_duration.py`.
    """
    acumulado = 0.0
    resultado: dict[int, float] = {}
    for ordem in ordens_ordenadas:
        acumulado += previsao_por_ordem.get(ordem, 0.0)
        resultado[ordem] = acumulado
    return resultado


def calcular_atraso_acumulado(
    *,
    chegou_em_atual: datetime.datetime,
    iniciada_em: datetime.datetime,
    previsto_acumulado_segundos: float,
) -> int:
    """`atraso_acumulado_segundos` — só diagnóstico/exibição, ver docstring do módulo."""
    real_decorrido_segundos = (chegou_em_atual - iniciada_em).total_seconds()
    return round(real_decorrido_segundos - previsto_acumulado_segundos)


def projetar_cauda(
    *,
    anchor_timestamp: datetime.datetime,
    ordem_anchor: int,
    ordens_a_percorrer: Sequence[int],
    previsao_por_ordem: Mapping[int, float],
    trip_students_pendentes_por_ordem: Mapping[int, Sequence[uuid.UUID]],
    atraso_manual_segundos: int,
) -> dict[uuid.UUID, datetime.datetime]:
    """ETA de cada trip_student ainda não resolvido.

    `ordens_a_percorrer`: TODAS as ordens da viagem maiores que `ordem_anchor`,
    crescente — precisa incluir também as de alunos já terminais (ausente),
    porque o trecho físico ainda é percorrido mesmo que ninguém desça ali;
    só não geramos ETA de saída para quem já está resolvido.
    `trip_students_pendentes_por_ordem`: só os NÃO terminais, é o que decide
    para quem o resultado tem entrada.
    """
    resultado: dict[uuid.UUID, datetime.datetime] = {}
    acumulado_segundos = 0.0
    for ordem in ordens_a_percorrer:
        if ordem <= ordem_anchor:
            continue
        acumulado_segundos += previsao_por_ordem.get(ordem, 0.0)
        eta = anchor_timestamp + datetime.timedelta(seconds=acumulado_segundos + atraso_manual_segundos)
        for trip_student_id in trip_students_pendentes_por_ordem.get(ordem, ()):
            resultado[trip_student_id] = eta
    return resultado
