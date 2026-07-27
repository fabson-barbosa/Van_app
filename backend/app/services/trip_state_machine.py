"""Máquina de estados do aluno na viagem — lógica pura (CLAUDE.md §4, Bloco B2).

Sem HTTP, sem sessão de banco: cada função recebe os objetos ORM já
carregados (não persistidos aqui) e os relógios como parâmetro, para que os
testes unitários rodem sem banco e de forma determinística. Quem persiste
(`db.add`/`db.commit`) é a camada fina em `api/viagens.py`.

Regras cobertas (CLAUDE.md §4, §7.1, §7.2, §8):
- Transições válidas da máquina de estados, incluindo `ausente` direto de
  `aguardando` (aluno pulado, sem dwell) e `desfazer_checkin` (janela de 60s).
- §7.2: bloquear Cheguei se houver parada anterior (ordem menor) pendente em
  `chegou` na mesma viagem.
- §7.1: varredura final bloqueante — não finalizar com aluno em estado não
  terminal.
- §8: reordenar só é permitido com o aluno ainda em `aguardando`.

Dois relógios (Bloco B4, ver `app/services/reconciliacao.py` e docstring de
`app/models/evento_aluno.py`): `ocorrido_em` é o instante reconciliado do
evento (o que alimenta `chegou_em`/`checkin_em`/etc e, por consequência, o
motor de tempos do B3); `registrado_em` é o relógio do servidor no momento
do processamento HTTP — é contra ELE, sempre, que a janela de 60s do
desfazer-checkin é medida, nunca contra o aparelho (undo infinito com
relógio manipulado seria possível do contrário).
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
    ocorrido_em: datetime.datetime,
    registrado_em: datetime.datetime,
    device_timestamp: datetime.datetime | None,
    event_id: uuid.UUID | None,
    registrado_por: uuid.UUID | None,
    estado_anterior: TripStudentEstado,
) -> EventoAluno:
    kwargs = dict(
        tenant_id=alvo.tenant_id,
        trip_student_id=alvo.id,
        tipo=tipo,
        estado_anterior=estado_anterior,
        ocorrido_em=ocorrido_em,
        registrado_em=registrado_em,
        device_timestamp=device_timestamp,
        registrado_por_user_id=registrado_por,
    )
    if event_id is not None:
        kwargs["event_id"] = event_id
    return EventoAluno(**kwargs)


# ---------------------------------------------------------------------------
# Eventos do aluno
# ---------------------------------------------------------------------------


def registrar_cheguei(
    viagem: Viagem,
    alvo: TripStudent,
    trip_students_viagem: Sequence[TripStudent],
    *,
    ocorrido_em: datetime.datetime,
    registrado_em: datetime.datetime,
    device_timestamp: datetime.datetime | None = None,
    event_id: uuid.UUID | None = None,
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
    alvo.chegou_em = ocorrido_em
    return _novo_evento(
        alvo, EventoAlunoTipo.CHEGUEI, ocorrido_em=ocorrido_em, registrado_em=registrado_em,
        device_timestamp=device_timestamp, event_id=event_id,
        registrado_por=registrado_por, estado_anterior=estado_anterior,
    )


def registrar_checkin(
    viagem: Viagem,
    alvo: TripStudent,
    *,
    ocorrido_em: datetime.datetime,
    registrado_em: datetime.datetime,
    device_timestamp: datetime.datetime | None = None,
    event_id: uuid.UUID | None = None,
    registrado_por: uuid.UUID | None = None,
) -> EventoAluno:
    _garantir_status_viagem(viagem, ViagemStatus.EM_ANDAMENTO, "checkin")
    if alvo.estado != TripStudentEstado.CHEGOU:
        raise TransicaoInvalidaError(alvo.estado, "checkin")

    estado_anterior = alvo.estado
    alvo.estado = TripStudentEstado.A_BORDO
    alvo.checkin_em = ocorrido_em
    alvo.checkin_registrado_em = registrado_em
    return _novo_evento(
        alvo, EventoAlunoTipo.CHECKIN, ocorrido_em=ocorrido_em, registrado_em=registrado_em,
        device_timestamp=device_timestamp, event_id=event_id,
        registrado_por=registrado_por, estado_anterior=estado_anterior,
    )


def registrar_checkout(
    viagem: Viagem,
    alvo: TripStudent,
    *,
    ocorrido_em: datetime.datetime,
    registrado_em: datetime.datetime,
    device_timestamp: datetime.datetime | None = None,
    event_id: uuid.UUID | None = None,
    registrado_por: uuid.UUID | None = None,
) -> EventoAluno:
    _garantir_status_viagem(viagem, ViagemStatus.EM_ANDAMENTO, "checkout")
    if alvo.estado != TripStudentEstado.A_BORDO:
        raise TransicaoInvalidaError(alvo.estado, "checkout")

    estado_anterior = alvo.estado
    alvo.estado = TripStudentEstado.ENTREGUE
    alvo.checkout_em = ocorrido_em
    return _novo_evento(
        alvo, EventoAlunoTipo.CHECKOUT, ocorrido_em=ocorrido_em, registrado_em=registrado_em,
        device_timestamp=device_timestamp, event_id=event_id,
        registrado_por=registrado_por, estado_anterior=estado_anterior,
    )


def registrar_ausente(
    viagem: Viagem,
    alvo: TripStudent,
    *,
    ocorrido_em: datetime.datetime,
    registrado_em: datetime.datetime,
    device_timestamp: datetime.datetime | None = None,
    event_id: uuid.UUID | None = None,
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
    alvo.ausente_em = ocorrido_em
    return _novo_evento(
        alvo, EventoAlunoTipo.AUSENTE, ocorrido_em=ocorrido_em, registrado_em=registrado_em,
        device_timestamp=device_timestamp, event_id=event_id,
        registrado_por=registrado_por, estado_anterior=estado_anterior,
    )


def desfazer_chegada(
    viagem: Viagem,
    alvo: TripStudent,
    *,
    ocorrido_em: datetime.datetime,
    registrado_em: datetime.datetime,
    device_timestamp: datetime.datetime | None = None,
    event_id: uuid.UUID | None = None,
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
        alvo, EventoAlunoTipo.DESFAZER_CHEGADA, ocorrido_em=ocorrido_em, registrado_em=registrado_em,
        device_timestamp=device_timestamp, event_id=event_id,
        registrado_por=registrado_por, estado_anterior=estado_anterior,
    )


def desfazer_checkin(
    viagem: Viagem,
    alvo: TripStudent,
    *,
    ocorrido_em: datetime.datetime,
    registrado_em: datetime.datetime,
    device_timestamp: datetime.datetime | None = None,
    event_id: uuid.UUID | None = None,
    registrado_por: uuid.UUID | None = None,
    janela_segundos: int = JANELA_DESFAZER_CHECKIN_SEGUNDOS,
) -> EventoAluno:
    """`a_bordo` -> `chegou`, dentro da janela de tolerância do servidor.

    A janela de 60s compara DOIS relógios de servidor — `registrado_em`
    (agora) contra `alvo.checkin_registrado_em` (quando o servidor recebeu
    aquele Checkin) — nunca `checkin_em` (que é o instante RECONCILIADO,
    logo influenciável pelo `device_timestamp`/`device_enviado_em` que o
    próprio cliente envia). Decisão de produto (CLAUDE.md §4, Bloco B4):
    medir contra qualquer valor de origem no aparelho abriria undo infinito
    com relógio manipulado. Um Checkin que ficou na fila offline por mais de
    60s antes de sincronizar (ou cujo desfazer só sincronizou depois desse
    prazo) é legitimamente rejeitado aqui — a bandeja de conflitos do app
    trata esse 409. `checkin_registrado_em` ausente (nunca deveria acontecer
    para um `trip_student` em `a_bordo`, mas cobre o backfill de viagens já
    em andamento no momento da migration) trata como janela expirada —
    fail-safe, nunca fail-open.

    Reabre o dwell e cancela o cronômetro do trajeto (na prática: limpa
    `checkin_em`, para que qualquer leitura de dwell/trajeto volte a não
    encontrar um Checkin fechado).
    """
    _garantir_status_viagem(viagem, ViagemStatus.EM_ANDAMENTO, "desfazer_checkin")
    if alvo.estado != TripStudentEstado.A_BORDO or alvo.checkin_em is None:
        raise TransicaoInvalidaError(alvo.estado, "desfazer_checkin")

    if alvo.checkin_registrado_em is None:
        raise JanelaDesfazerExpiradaError(janela_segundos, float("inf"))

    decorrido = (registrado_em - alvo.checkin_registrado_em).total_seconds()
    if decorrido > janela_segundos:
        raise JanelaDesfazerExpiradaError(janela_segundos, decorrido)

    estado_anterior = alvo.estado
    alvo.estado = TripStudentEstado.CHEGOU
    alvo.checkin_em = None
    alvo.checkin_registrado_em = None
    return _novo_evento(
        alvo, EventoAlunoTipo.DESFAZER_CHECKIN, ocorrido_em=ocorrido_em, registrado_em=registrado_em,
        device_timestamp=device_timestamp, event_id=event_id,
        registrado_por=registrado_por, estado_anterior=estado_anterior,
    )


# ---------------------------------------------------------------------------
# Ciclo de vida da viagem
# ---------------------------------------------------------------------------


def iniciar_viagem(
    viagem: Viagem,
    alunos_paradas: Sequence[tuple[uuid.UUID, uuid.UUID | None, int]],
    *,
    ocorrido_em: datetime.datetime,
) -> list[TripStudent]:
    """`planejada` -> `em_andamento`; monta os `trip_students` a partir do
    gabarito da rota, congelando `ordem`/`parada_id` (snapshot — CLAUDE.md §8).

    `alunos_paradas`: tuplas `(aluno_id, parada_id, ordem)` já resolvidas pelo
    chamador (join Aluno/Parada por rota_id) — a query em si é responsabilidade
    da camada de API, não deste núcleo. `ocorrido_em` é o instante reconciliado
    do toque em "iniciar rota" (Bloco B4) — é a âncora que `pos_evento.py` usa
    quando não há parada anterior, então também passa pela reconciliação.
    """
    _garantir_status_viagem(viagem, ViagemStatus.PLANEJADA, "iniciar")

    viagem.status = ViagemStatus.EM_ANDAMENTO
    viagem.iniciada_em = ocorrido_em

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
    ocorrido_em: datetime.datetime,
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
    viagem.finalizada_em = ocorrido_em
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
