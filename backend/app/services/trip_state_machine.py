"""Máquina de estados do aluno na viagem — lógica pura (CLAUDE.md §4, Bloco B2).

Sem HTTP, sem sessão de banco: cada função recebe os objetos ORM já
carregados (não persistidos aqui) e o relógio (`now`) como parâmetro, para
que os testes unitários rodem sem banco e de forma determinística. Quem
persiste (`db.add`/`db.commit`) é a camada fina em `api/viagens.py`.

Regras cobertas (CLAUDE.md §4, §7.1, §7.2, §8):
- Transições válidas da máquina de estados, incluindo `ausente` direto de
  `aguardando` (aluno pulado, sem dwell) e `desfazer_checkin` (janela de 60s).
- §7.2: bloquear Cheguei se houver parada anterior (ordem menor) pendente em
  `chegou` na mesma viagem.
- §7.1: varredura final bloqueante — não finalizar com aluno em estado não
  terminal.
- §8: reordenar só é permitido com o aluno ainda em `aguardando`.
"""
from __future__ import annotations

import datetime
import uuid
from typing import Sequence

from app.models.evento_aluno import EventoAluno, EventoAlunoTipo
from app.models.trip_student import TripStudent, TripStudentEstado
from app.models.viagem import Viagem, ViagemStatus
from app.services.exceptions import (
    JanelaDesfazerExpiradaError,
    ParadaAnteriorPendenteError,
    ReordenacaoInvalidaError,
    TransicaoInvalidaError,
    TripStudentDesconhecidoError,
    VarreduraFinalPendenteError,
    ViagemStatusInvalidoError,
)

JANELA_DESFAZER_CHECKIN_SEGUNDOS = 60

_ESTADOS_TERMINAIS = (TripStudentEstado.ENTREGUE, TripStudentEstado.AUSENTE)


def _garantir_status_viagem(viagem: Viagem, esperado: ViagemStatus, acao: str) -> None:
    if viagem.status != esperado:
        raise ViagemStatusInvalidoError(viagem.status, esperado, acao)


def _novo_evento(
    alvo: TripStudent,
    tipo: EventoAlunoTipo,
    *,
    now: datetime.datetime,
    device_timestamp: datetime.datetime | None,
    registrado_por: uuid.UUID | None,
    estado_anterior: TripStudentEstado,
) -> EventoAluno:
    return EventoAluno(
        tenant_id=alvo.tenant_id,
        trip_student_id=alvo.id,
        tipo=tipo,
        estado_anterior=estado_anterior,
        timestamp=now,
        device_timestamp=device_timestamp,
        registrado_por_user_id=registrado_por,
    )


# ---------------------------------------------------------------------------
# Eventos do aluno
# ---------------------------------------------------------------------------


def registrar_cheguei(
    viagem: Viagem,
    alvo: TripStudent,
    trip_students_viagem: Sequence[TripStudent],
    *,
    now: datetime.datetime,
    device_timestamp: datetime.datetime | None = None,
    registrado_por: uuid.UUID | None = None,
) -> EventoAluno:
    _garantir_status_viagem(viagem, ViagemStatus.EM_ANDAMENTO, "cheguei")
    if alvo.estado != TripStudentEstado.AGUARDANDO:
        raise TransicaoInvalidaError(alvo.estado, "cheguei")

    pendentes = [
        ts
        for ts in trip_students_viagem
        if ts.id != alvo.id and ts.estado == TripStudentEstado.CHEGOU and ts.ordem < alvo.ordem
    ]
    if pendentes:
        raise ParadaAnteriorPendenteError(pendentes)

    estado_anterior = alvo.estado
    alvo.estado = TripStudentEstado.CHEGOU
    alvo.chegou_em = now
    return _novo_evento(
        alvo, EventoAlunoTipo.CHEGUEI, now=now, device_timestamp=device_timestamp,
        registrado_por=registrado_por, estado_anterior=estado_anterior,
    )


def registrar_checkin(
    viagem: Viagem,
    alvo: TripStudent,
    *,
    now: datetime.datetime,
    device_timestamp: datetime.datetime | None = None,
    registrado_por: uuid.UUID | None = None,
) -> EventoAluno:
    _garantir_status_viagem(viagem, ViagemStatus.EM_ANDAMENTO, "checkin")
    if alvo.estado != TripStudentEstado.CHEGOU:
        raise TransicaoInvalidaError(alvo.estado, "checkin")

    estado_anterior = alvo.estado
    alvo.estado = TripStudentEstado.A_BORDO
    alvo.checkin_em = now
    return _novo_evento(
        alvo, EventoAlunoTipo.CHECKIN, now=now, device_timestamp=device_timestamp,
        registrado_por=registrado_por, estado_anterior=estado_anterior,
    )


def registrar_checkout(
    viagem: Viagem,
    alvo: TripStudent,
    *,
    now: datetime.datetime,
    device_timestamp: datetime.datetime | None = None,
    registrado_por: uuid.UUID | None = None,
) -> EventoAluno:
    _garantir_status_viagem(viagem, ViagemStatus.EM_ANDAMENTO, "checkout")
    if alvo.estado != TripStudentEstado.A_BORDO:
        raise TransicaoInvalidaError(alvo.estado, "checkout")

    estado_anterior = alvo.estado
    alvo.estado = TripStudentEstado.ENTREGUE
    alvo.checkout_em = now
    return _novo_evento(
        alvo, EventoAlunoTipo.CHECKOUT, now=now, device_timestamp=device_timestamp,
        registrado_por=registrado_por, estado_anterior=estado_anterior,
    )


def registrar_ausente(
    viagem: Viagem,
    alvo: TripStudent,
    *,
    now: datetime.datetime,
    device_timestamp: datetime.datetime | None = None,
    registrado_por: uuid.UUID | None = None,
) -> EventoAluno:
    """`aguardando` ou `chegou` -> `ausente` (CLAUDE.md §4).

    Vindo de `aguardando`, não existe `chegou_em` — não há dwell, e não deve
    ser gravado nem como zero. `estado_anterior` no evento é o que permite
    distinguir os dois casos depois (pulado vs. chegou e não embarcou).
    """
    _garantir_status_viagem(viagem, ViagemStatus.EM_ANDAMENTO, "ausente")
    if alvo.estado not in (TripStudentEstado.AGUARDANDO, TripStudentEstado.CHEGOU):
        raise TransicaoInvalidaError(alvo.estado, "ausente")

    estado_anterior = alvo.estado
    alvo.estado = TripStudentEstado.AUSENTE
    alvo.ausente_em = now
    return _novo_evento(
        alvo, EventoAlunoTipo.AUSENTE, now=now, device_timestamp=device_timestamp,
        registrado_por=registrado_por, estado_anterior=estado_anterior,
    )


def desfazer_chegada(
    viagem: Viagem,
    alvo: TripStudent,
    *,
    now: datetime.datetime,
    device_timestamp: datetime.datetime | None = None,
    registrado_por: uuid.UUID | None = None,
) -> EventoAluno:
    """`chegou` -> `aguardando`, permitido enquanto não houver Checkin.

    Não dispara notificação de correção (CLAUDE.md §4) — isso é responsabilidade
    da camada de notificação (B3), que simplesmente não deve reagir a este tipo
    de evento.
    """
    _garantir_status_viagem(viagem, ViagemStatus.EM_ANDAMENTO, "desfazer_chegada")
    if alvo.estado != TripStudentEstado.CHEGOU:
        raise TransicaoInvalidaError(alvo.estado, "desfazer_chegada")

    estado_anterior = alvo.estado
    alvo.estado = TripStudentEstado.AGUARDANDO
    alvo.chegou_em = None
    return _novo_evento(
        alvo, EventoAlunoTipo.DESFAZER_CHEGADA, now=now, device_timestamp=device_timestamp,
        registrado_por=registrado_por, estado_anterior=estado_anterior,
    )


def desfazer_checkin(
    viagem: Viagem,
    alvo: TripStudent,
    *,
    now: datetime.datetime,
    device_timestamp: datetime.datetime | None = None,
    registrado_por: uuid.UUID | None = None,
    janela_segundos: int = JANELA_DESFAZER_CHECKIN_SEGUNDOS,
) -> EventoAluno:
    """`a_bordo` -> `chegou`, dentro da janela de tolerância do servidor.

    Reabre o dwell e cancela o cronômetro do trajeto (na prática: limpa
    `checkin_em`, para que qualquer leitura de dwell/trajeto volte a não
    encontrar um Checkin fechado).
    """
    _garantir_status_viagem(viagem, ViagemStatus.EM_ANDAMENTO, "desfazer_checkin")
    if alvo.estado != TripStudentEstado.A_BORDO or alvo.checkin_em is None:
        raise TransicaoInvalidaError(alvo.estado, "desfazer_checkin")

    decorrido = (now - alvo.checkin_em).total_seconds()
    if decorrido > janela_segundos:
        raise JanelaDesfazerExpiradaError(janela_segundos, decorrido)

    estado_anterior = alvo.estado
    alvo.estado = TripStudentEstado.CHEGOU
    alvo.checkin_em = None
    return _novo_evento(
        alvo, EventoAlunoTipo.DESFAZER_CHECKIN, now=now, device_timestamp=device_timestamp,
        registrado_por=registrado_por, estado_anterior=estado_anterior,
    )


# ---------------------------------------------------------------------------
# Ciclo de vida da viagem
# ---------------------------------------------------------------------------


def iniciar_viagem(
    viagem: Viagem,
    alunos_paradas: Sequence[tuple[uuid.UUID, uuid.UUID | None, int]],
    *,
    now: datetime.datetime,
) -> list[TripStudent]:
    """`planejada` -> `em_andamento`; monta os `trip_students` a partir do
    gabarito da rota, congelando `ordem`/`parada_id` (snapshot — CLAUDE.md §8).

    `alunos_paradas`: tuplas `(aluno_id, parada_id, ordem)` já resolvidas pelo
    chamador (join Aluno/Parada por rota_id) — a query em si é responsabilidade
    da camada de API, não deste núcleo.
    """
    _garantir_status_viagem(viagem, ViagemStatus.PLANEJADA, "iniciar")

    viagem.status = ViagemStatus.EM_ANDAMENTO
    viagem.iniciada_em = now

    return [
        TripStudent(
            tenant_id=viagem.tenant_id,
            viagem_id=viagem.id,
            aluno_id=aluno_id,
            parada_id=parada_id,
            ordem=ordem,
            estado=TripStudentEstado.AGUARDANDO,
        )
        for aluno_id, parada_id, ordem in alunos_paradas
    ]


def finalizar_viagem(
    viagem: Viagem,
    trip_students: Sequence[TripStudent],
    *,
    now: datetime.datetime,
) -> None:
    """Varredura final bloqueante (CLAUDE.md §7.1 — regra inviolável).

    Não finaliza enquanto houver aluno em estado não terminal. Quando algum
    estiver `a_bordo`, a exceção sinaliza `algum_a_bordo=True` para que a
    camada de API dispare o alerta duro + notificação ao gestor (a notificação
    em si é integração de um bloco futuro; aqui garantimos que a informação
    não se perde).
    """
    _garantir_status_viagem(viagem, ViagemStatus.EM_ANDAMENTO, "finalizar")

    pendentes = [ts for ts in trip_students if ts.estado not in _ESTADOS_TERMINAIS]
    if pendentes:
        algum_a_bordo = any(ts.estado == TripStudentEstado.A_BORDO for ts in pendentes)
        raise VarreduraFinalPendenteError(pendentes, algum_a_bordo)

    viagem.status = ViagemStatus.FINALIZADA
    viagem.finalizada_em = now
    viagem.varredura_confirmada = True


def reordenar(
    viagem: Viagem,
    trip_students_alvo: Sequence[TripStudent],
    nova_ordem: dict[uuid.UUID, int],
) -> None:
    """Reordenação de paradas antes do Cheguei (CLAUDE.md §8).

    Só é permitida enquanto o aluno ainda está `aguardando` — depois disso o
    trajeto já foi atribuído ao par de paradas errado se a ordem mudar.
    `trip_students_alvo` deve conter exatamente os `trip_student`s referenciados
    em `nova_ordem` (resolvidos pelo chamador); ids que não aparecem viram
    `TripStudentDesconhecidoError`.
    """
    _garantir_status_viagem(viagem, ViagemStatus.EM_ANDAMENTO, "reordenar")

    encontrados = {ts.id: ts for ts in trip_students_alvo}
    desconhecidos = [tid for tid in nova_ordem if tid not in encontrados]
    if desconhecidos:
        raise TripStudentDesconhecidoError(desconhecidos)

    invalidos = [ts for ts in trip_students_alvo if ts.estado != TripStudentEstado.AGUARDANDO]
    if invalidos:
        raise ReordenacaoInvalidaError(invalidos)

    for trip_student_id, ordem in nova_ordem.items():
        encontrados[trip_student_id].ordem = ordem
