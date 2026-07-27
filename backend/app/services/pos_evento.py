"""Orquestração pós-evento — motor de tempos + cascata de notificações (Bloco B3).

Chamado pela API (`app/api/viagens.py`) logo depois de cada transição da
máquina de estados (`services/trip_state_machine.py`) suceder, ANTES do
commit — mesma transação do evento que a originou (assim um erro no meio
desfaz tudo junto, e a amostra/notificação nunca fica "solta" de um evento
que não foi persistido).

Ponte entre a lógica pura (`leg_duration.py`, `projecao.py`, `notificacoes.py`
— sem sessão de banco, testável isolado) e o banco: busca o que falta, aplica
as funções puras, grava o resultado. Este módulo em si só é testável com
banco real (`tests/integration/`).

Limitação aceita e documentada (não resolvida nesta rodada): desfazer um
evento (`desfazer_chegada`/`desfazer_checkin`) DEPOIS que uma amostra de
`leg_duration` já foi gravada a partir dele não desfaz a amostra — reverter
uma média EWMA já misturada exigiria guardar todo o histórico de amostras, o
que não foi pedido. O impacto é pequeno (uma amostra ligeiramente
contaminada, auto-corrigida com o tempo) e a janela é curta (60s para
desfazer checkin).
"""
from __future__ import annotations

import datetime
import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.aluno import Responsavel
from app.models.leg_duration import LegDuration
from app.models.notificacao import NotificacaoAgendada, NotificacaoEstado, NotificacaoTipo
from app.models.rota import Parada
from app.models.trip_student import TripStudent, TripStudentEstado
from app.models.viagem import Viagem
from app.services import leg_duration as ld
from app.services import notificacoes as notif
from app.services import projecao as proj

_ESTADOS_TERMINAIS = (TripStudentEstado.ENTREGUE, TripStudentEstado.AUSENTE)

# Antecedência do aviso de preparo — parâmetro de produto, registrado em
# CLAUDE.md §5 (senão o B4 reinventa): PISO de 5min antes do ETA da
# parada-alvo, mas a âncora real é POSICIONAL (~2 paradas antes), não
# temporal — o preparo nunca pode ser agendado para depois do ETA da parada
# FISICAMENTE anterior ao alvo (`_eta_parada_anterior`/`_agendado_para_preparo`
# abaixo). Em trechos curtos isso encurta a antecedência efetiva para menos
# de 5min — nunca inverte com "é a próxima" (iminência), que dispara quando
# o van chega nessa parada anterior.
PREPARO_ANTECEDENCIA_SEGUNDOS = 5 * 60


# ---------------------------------------------------------------------------
# Posicionamento — só a lista já carregada, sem banco
# ---------------------------------------------------------------------------


def _nao_terminais_apos(trip_students_ordenados: Sequence[TripStudent], ordem_apos: int) -> list[TripStudent]:
    candidatos = [ts for ts in trip_students_ordenados if ts.ordem > ordem_apos and ts.estado not in _ESTADOS_TERMINAIS]
    return sorted(candidatos, key=lambda ts: ts.ordem)


def _n_esimo_nao_terminal(
    trip_students_ordenados: Sequence[TripStudent], ordem_apos: int, posicao: int
) -> TripStudent | None:
    """`posicao=1` -> próximo não-terminal (N+1); `posicao=2` -> o depois desse
    (N+2). CLAUDE.md §5 usa "N+1"/"N+2" no sentido de próximas paradas ainda
    pendentes, não literalmente `ordem+1`/`ordem+2` — pula quem já é terminal
    (ex.: `ausente`), já que notificar o responsável de quem não vem não faz
    sentido."""
    candidatos = _nao_terminais_apos(trip_students_ordenados, ordem_apos)
    if posicao < 1 or posicao > len(candidatos):
        return None
    return candidatos[posicao - 1]


def _ordem_anterior_info(
    trip_students_ordenados: Sequence[TripStudent], ordem_atual: int
) -> tuple[int | None, datetime.datetime | None]:
    """`(ordem_anterior, checkin_em_ancora)` do trecho imediatamente antes de
    `ordem_atual`. `checkin_em_ancora=None` com `ordem_anterior` não-None
    significa "existe parada anterior mas foi pulada" (ninguém lá tem
    checkin_em) — sinal para o chamador descartar a amostra (CLAUDE.md §4).
    `(None, None)` significa que não há parada anterior (`ordem_atual` é a
    primeira da viagem) — o chamador usa `viagem.iniciada_em` como âncora.
    """
    anteriores = [ts for ts in trip_students_ordenados if ts.ordem < ordem_atual]
    if not anteriores:
        return None, None
    ordem_anterior = max(ts.ordem for ts in anteriores)
    mesma_ordem = [ts for ts in anteriores if ts.ordem == ordem_anterior]
    checkins_validos = [ts.checkin_em for ts in mesma_ordem if ts.checkin_em is not None]
    return ordem_anterior, (max(checkins_validos) if checkins_validos else None)


def _anchor_atual(
    trip_students_ordenados: Sequence[TripStudent], iniciada_em: datetime.datetime
) -> tuple[datetime.datetime, int]:
    """Onde a viagem está "agora": o timestamp mais recente entre todos os
    eventos reais já ocorridos, e a maior `ordem` que já foi tocada. `-1`
    como ordem-sentinela de "nada aconteceu ainda" (ordem_base é >= 0 no
    schema, então 0 já é um valor real — não pode ser o sentinela)."""
    timestamps: list[datetime.datetime] = []
    ordens_tocadas: list[int] = []
    for ts in trip_students_ordenados:
        candidatos = [t for t in (ts.chegou_em, ts.checkin_em, ts.checkout_em, ts.ausente_em) if t is not None]
        if candidatos:
            timestamps.extend(candidatos)
            ordens_tocadas.append(ts.ordem)
    if not timestamps:
        return iniciada_em, -1
    return max(timestamps), max(ordens_tocadas)


def _eta_parada_anterior(
    ordens_a_percorrer: Sequence[int], etas_ordem: dict[int, datetime.datetime],
    anchor_timestamp: datetime.datetime, ordem_alvo: int,
) -> datetime.datetime:
    """Teto de agendamento do `preparo` (CLAUDE.md §5): ETA da parada
    FISICAMENTE anterior a `ordem_alvo` — nunca depois disso, senão o
    preparo chegaria depois de "é a próxima" (que dispara quando o van
    chega nessa parada anterior). Sem parada intermediária entre a âncora e
    o alvo (alvo é literalmente a próxima), o teto é a própria âncora."""
    anteriores = [o for o in ordens_a_percorrer if o < ordem_alvo]
    if not anteriores:
        return anchor_timestamp
    return etas_ordem[max(anteriores)]


def _agendado_para_preparo(
    *, agora: datetime.datetime, eta_alvo: datetime.datetime, eta_parada_anterior: datetime.datetime,
    antecedencia_segundos: int = PREPARO_ANTECEDENCIA_SEGUNDOS,
) -> datetime.datetime:
    """Quando o `preparo` deve disparar — CLAUDE.md §5.

    Piso: nunca no passado (`agora`). Teto: nunca depois do ETA da parada
    fisicamente anterior ao alvo (`eta_parada_anterior` < `eta_alvo` sempre,
    por construção de `etas_por_ordem`) — é isso que garante a ordem da
    cascata em trechos curtos, onde os 5min de antecedência desejados não
    cabem. O piso nunca ultrapassa o teto porque `eta_parada_anterior >= agora`
    sempre (é uma ETA futura a partir da mesma âncora).
    """
    candidato = eta_alvo - datetime.timedelta(seconds=antecedencia_segundos)
    return min(max(agora, candidato), eta_parada_anterior)


# ---------------------------------------------------------------------------
# Leg duration — leitura agregada (progressiva) + gravação de amostra
# ---------------------------------------------------------------------------


def _estimativa_seed(db: Session, trip_student: TripStudent) -> float:
    if trip_student.parada_id is None:
        return float(ld.ESTIMATIVA_PADRAO_SEGUNDOS)
    parada = db.get(Parada, trip_student.parada_id)
    if parada is None or parada.duracao_estimada_segundos is None:
        return float(ld.ESTIMATIVA_PADRAO_SEGUNDOS)
    return float(parada.duracao_estimada_segundos)


def _bucket_exato(db: Session, rota_id: uuid.UUID, ordem: int, dia_semana: int, faixa_horaria: int) -> LegDuration | None:
    return db.scalars(
        select(LegDuration).where(
            LegDuration.rota_id == rota_id,
            LegDuration.ordem == ordem,
            LegDuration.dia_semana == dia_semana,
            LegDuration.faixa_horaria == faixa_horaria,
        )
    ).first()


def _agregado(db: Session, rota_id: uuid.UUID, ordem: int, dia_semana: int | None) -> ld.BucketStats:
    stmt = select(
        func.sum(LegDuration.segundos_media * LegDuration.amostras), func.sum(LegDuration.amostras)
    ).where(LegDuration.rota_id == rota_id, LegDuration.ordem == ordem)
    if dia_semana is not None:
        stmt = stmt.where(LegDuration.dia_semana == dia_semana)
    soma_ponderada, soma_amostras = db.execute(stmt).one()
    if not soma_amostras:
        return ld.BucketStats(segundos_media=0.0, amostras=0)
    return ld.BucketStats(segundos_media=soma_ponderada / soma_amostras, amostras=soma_amostras)


def prever_segundos_leg(
    db: Session, rota_id: uuid.UUID, ordem: int, momento: datetime.datetime, estimativa_seed_segundos: float
) -> float:
    """Agregação progressiva NA LEITURA (CLAUDE.md §5) para um único trecho."""
    dia_semana, faixa_horaria = momento.weekday(), momento.hour
    exato = _bucket_exato(db, rota_id, ordem, dia_semana, faixa_horaria)
    exato_stats = ld.BucketStats(exato.segundos_media, exato.amostras) if exato is not None else None
    return ld.escolher_estimativa(
        exato=exato_stats,
        agregado_dia=_agregado(db, rota_id, ordem, dia_semana),
        agregado_geral=_agregado(db, rota_id, ordem, None),
        estimativa_seed_segundos=estimativa_seed_segundos,
    )


def _previsao_todos_os_trechos(
    db: Session, viagem: Viagem, trip_students_ordenados: Sequence[TripStudent], momento: datetime.datetime
) -> dict[int, float]:
    resultado: dict[int, float] = {}
    for ts in trip_students_ordenados:
        if ts.ordem in resultado:
            continue
        seed = _estimativa_seed(db, ts)
        resultado[ts.ordem] = prever_segundos_leg(db, viagem.rota_id, ts.ordem, momento, seed)
    return resultado


def _registrar_amostra_trajeto(
    db: Session, viagem: Viagem, trip_students_ordenados: Sequence[TripStudent], atual: TripStudent
) -> None:
    """Cheguei(atual) => amostra de trajeto = Cheguei(atual) - Checkin(anterior)
    (CLAUDE.md §5). Descarta sem gravar nada se a parada anterior foi pulada."""
    ordem_anterior, anchor = _ordem_anterior_info(trip_students_ordenados, atual.ordem)
    if ordem_anterior is None:
        anchor = viagem.iniciada_em
    elif anchor is None:
        return  # casa anterior pulada — trajeto não é amostra válida (CLAUDE.md §4)

    segundos = (atual.chegou_em - anchor).total_seconds()
    dia_semana, faixa_horaria = atual.chegou_em.weekday(), atual.chegou_em.hour

    estimativa_seed = _estimativa_seed(db, atual)
    bucket = _bucket_exato(db, viagem.rota_id, atual.ordem, dia_semana, faixa_horaria)
    bucket_stats = ld.BucketStats(bucket.segundos_media, bucket.amostras) if bucket is not None else None

    resultado = ld.registrar_amostra(bucket_stats, segundos, estimativa_seed)
    if resultado is None:
        return  # amostra inválida (negativa/outlier) — descartar

    if bucket is not None:
        bucket.segundos_media = resultado.segundos_media
        bucket.amostras = resultado.amostras
    else:
        db.add(LegDuration(
            tenant_id=viagem.tenant_id, rota_id=viagem.rota_id, ordem=atual.ordem,
            dia_semana=dia_semana, faixa_horaria=faixa_horaria,
            segundos_media=resultado.segundos_media, amostras=resultado.amostras,
        ))


# ---------------------------------------------------------------------------
# Notificações — recipientes, envio imediato, agendamento/cancelamento
# ---------------------------------------------------------------------------


def _responsaveis_notificaveis(db: Session, aluno_id: uuid.UUID) -> list[Responsavel]:
    responsaveis = db.scalars(select(Responsavel).where(Responsavel.aluno_id == aluno_id)).all()
    return [r for r in responsaveis if notif.deve_notificar(r.permissoes)]


def _enviar_imediata(
    db: Session, viagem: Viagem, trip_student: TripStudent, tipo: NotificacaoTipo, payload: dict,
    agora: datetime.datetime, sender: notif.FCMSender,
) -> None:
    for responsavel in _responsaveis_notificaveis(db, trip_student.aluno_id):
        db.add(NotificacaoAgendada(
            tenant_id=viagem.tenant_id, viagem_id=viagem.id, trip_student_id=trip_student.id,
            destinatario_user_id=responsavel.user_id, tipo=tipo, estado=NotificacaoEstado.ENVIADO,
            agendado_para=agora, enviado_em=agora, payload=payload,
        ))
        sender.enviar(destinatario_user_id=responsavel.user_id, tipo=tipo.value, payload=payload)


def _agendar_ou_atualizar_preparo(
    db: Session, viagem: Viagem, alvo: TripStudent, agendado_para: datetime.datetime, payload: dict
) -> None:
    for responsavel in _responsaveis_notificaveis(db, alvo.aluno_id):
        existente = db.scalars(
            select(NotificacaoAgendada).where(
                NotificacaoAgendada.trip_student_id == alvo.id,
                NotificacaoAgendada.destinatario_user_id == responsavel.user_id,
                NotificacaoAgendada.tipo == NotificacaoTipo.PREPARO,
                NotificacaoAgendada.estado == NotificacaoEstado.AGENDADO,
            )
        ).first()
        if existente is not None:
            existente.agendado_para = agendado_para
            existente.payload = payload
        else:
            db.add(NotificacaoAgendada(
                tenant_id=viagem.tenant_id, viagem_id=viagem.id, trip_student_id=alvo.id,
                destinatario_user_id=responsavel.user_id, tipo=NotificacaoTipo.PREPARO,
                estado=NotificacaoEstado.AGENDADO, agendado_para=agendado_para, payload=payload,
            ))


def _cancelar_preparo_pendente(db: Session, trip_student_id: uuid.UUID, motivo: str) -> None:
    pendentes = db.scalars(
        select(NotificacaoAgendada).where(
            NotificacaoAgendada.trip_student_id == trip_student_id,
            NotificacaoAgendada.tipo == NotificacaoTipo.PREPARO,
            NotificacaoAgendada.estado == NotificacaoEstado.AGENDADO,
        )
    ).all()
    for n in pendentes:
        n.estado = NotificacaoEstado.CANCELADO
        n.motivo_cancelamento = motivo


def _recalcular_e_reagendar(
    db: Session, viagem: Viagem, trip_students_ordenados: Sequence[TripStudent], agora: datetime.datetime
) -> None:
    """Roda depois de QUALQUER evento — recalcula a cauda a partir de onde a
    viagem está agora e reagenda (UPDATE, nunca linha nova) todo `preparo`
    ainda pendente cujo alvo continua não-terminal. CLAUDE.md §5, gatilho
    "recálculo que invalide o horário"."""
    anchor_timestamp, ordem_anchor = _anchor_atual(trip_students_ordenados, viagem.iniciada_em)
    previsao_por_ordem = _previsao_todos_os_trechos(db, viagem, trip_students_ordenados, agora)
    ordens_a_percorrer = sorted({ts.ordem for ts in trip_students_ordenados if ts.ordem > ordem_anchor})
    etas_ordem = proj.etas_por_ordem(
        anchor_timestamp=anchor_timestamp, ordem_anchor=ordem_anchor, ordens_a_percorrer=ordens_a_percorrer,
        previsao_por_ordem=previsao_por_ordem, atraso_manual_segundos=viagem.atraso_manual_segundos,
    )
    por_id = {ts.id: ts for ts in trip_students_ordenados}

    pendentes_preparo = db.scalars(
        select(NotificacaoAgendada).where(
            NotificacaoAgendada.viagem_id == viagem.id,
            NotificacaoAgendada.tipo == NotificacaoTipo.PREPARO,
            NotificacaoAgendada.estado == NotificacaoEstado.AGENDADO,
        )
    ).all()
    for pendente in pendentes_preparo:
        alvo = por_id.get(pendente.trip_student_id)
        if alvo is None or alvo.estado in _ESTADOS_TERMINAIS:
            continue  # virou terminal — cancelamento específico cuida disso
        eta_alvo = etas_ordem.get(alvo.ordem)
        if eta_alvo is None:
            continue  # fora da cauda calculada (ex.: ordem <= âncora)
        eta_parada_anterior = _eta_parada_anterior(ordens_a_percorrer, etas_ordem, anchor_timestamp, alvo.ordem)
        pendente.agendado_para = _agendado_para_preparo(
            agora=agora, eta_alvo=eta_alvo, eta_parada_anterior=eta_parada_anterior
        )
        antecedencia_real = (eta_alvo - pendente.agendado_para).total_seconds()
        pendente.payload = notif.montar_payload_preparo(antecedencia_real)


# ---------------------------------------------------------------------------
# Entradas por tipo de evento — chamadas por app/api/viagens.py
# ---------------------------------------------------------------------------


def processar_cheguei(
    db: Session, viagem: Viagem, trip_students_ordenados: Sequence[TripStudent], atual: TripStudent,
    agora: datetime.datetime, sender: notif.FCMSender | None = None,
) -> None:
    sender = sender or notif.StubFCMSender()

    _registrar_amostra_trajeto(db, viagem, trip_students_ordenados, atual)

    previsao_por_ordem = _previsao_todos_os_trechos(db, viagem, trip_students_ordenados, agora)
    previsto_acumulado = proj.previsao_acumulada_ate(sorted({ts.ordem for ts in trip_students_ordenados}), previsao_por_ordem)
    viagem.atraso_acumulado_segundos = proj.calcular_atraso_acumulado(
        chegou_em_atual=atual.chegou_em, iniciada_em=viagem.iniciada_em,
        previsto_acumulado_segundos=previsto_acumulado.get(atual.ordem, 0.0),
    )

    # Imediatas — CLAUDE.md §5/§6, sem delay cancelável.
    _enviar_imediata(db, viagem, atual, NotificacaoTipo.CHEGADA, {}, agora, sender)
    proximo = _n_esimo_nao_terminal(trip_students_ordenados, atual.ordem, 1)
    if proximo is not None:
        _enviar_imediata(db, viagem, proximo, NotificacaoTipo.IMINENCIA, {}, agora, sender)

    _recalcular_e_reagendar(db, viagem, trip_students_ordenados, agora)


def processar_checkin(
    db: Session, viagem: Viagem, trip_students_ordenados: Sequence[TripStudent], atual: TripStudent,
    agora: datetime.datetime,
) -> None:
    alvo = _n_esimo_nao_terminal(trip_students_ordenados, atual.ordem, 2)
    if alvo is not None:
        previsao_por_ordem = _previsao_todos_os_trechos(db, viagem, trip_students_ordenados, agora)
        ordens_a_percorrer = sorted({ts.ordem for ts in trip_students_ordenados if ts.ordem > atual.ordem})
        etas_ordem = proj.etas_por_ordem(
            anchor_timestamp=agora, ordem_anchor=atual.ordem, ordens_a_percorrer=ordens_a_percorrer,
            previsao_por_ordem=previsao_por_ordem, atraso_manual_segundos=viagem.atraso_manual_segundos,
        )
        eta_alvo = etas_ordem.get(alvo.ordem)
        if eta_alvo is not None:
            eta_parada_anterior = _eta_parada_anterior(ordens_a_percorrer, etas_ordem, agora, alvo.ordem)
            agendado_para = _agendado_para_preparo(agora=agora, eta_alvo=eta_alvo, eta_parada_anterior=eta_parada_anterior)
            antecedencia_real = (eta_alvo - agendado_para).total_seconds()
            _agendar_ou_atualizar_preparo(db, viagem, alvo, agendado_para, notif.montar_payload_preparo(antecedencia_real))

    _recalcular_e_reagendar(db, viagem, trip_students_ordenados, agora)


def processar_checkout(
    db: Session, viagem: Viagem, trip_students_ordenados: Sequence[TripStudent], atual: TripStudent,
    agora: datetime.datetime,
) -> None:
    _cancelar_preparo_pendente(db, atual.id, notif.MOTIVO_TERMINAL)
    _recalcular_e_reagendar(db, viagem, trip_students_ordenados, agora)


def processar_ausente(
    db: Session, viagem: Viagem, trip_students_ordenados: Sequence[TripStudent], atual: TripStudent,
    agora: datetime.datetime,
) -> None:
    _cancelar_preparo_pendente(db, atual.id, notif.MOTIVO_AUSENTE)
    _recalcular_e_reagendar(db, viagem, trip_students_ordenados, agora)


def processar_desfazer_chegada(
    db: Session, viagem: Viagem, trip_students_ordenados: Sequence[TripStudent], atual: TripStudent,
    agora: datetime.datetime,
) -> None:
    _recalcular_e_reagendar(db, viagem, trip_students_ordenados, agora)


def processar_desfazer_checkin(
    db: Session, viagem: Viagem, trip_students_ordenados: Sequence[TripStudent], atual: TripStudent,
    agora: datetime.datetime,
) -> None:
    # Recalcula quem seria "N+2 a partir de N" agora, para cancelar o preparo
    # que ESTE checkin havia agendado. Limitação aceita: se algo mudou a
    # posição de N+2 entre o checkin e o desfazer (janela de 60s), pode
    # cancelar o alvo "errado" (o recalculado, não o originalmente agendado)
    # — o próximo evento real corrige via `_recalcular_e_reagendar` de
    # qualquer forma.
    alvo = _n_esimo_nao_terminal(trip_students_ordenados, atual.ordem, 2)
    if alvo is not None:
        _cancelar_preparo_pendente(db, alvo.id, notif.MOTIVO_DESFAZER_CHECKIN)
    _recalcular_e_reagendar(db, viagem, trip_students_ordenados, agora)


def processar_reordenar(
    db: Session, viagem: Viagem, trip_students_ordenados: Sequence[TripStudent],
    reordenados: Sequence[TripStudent], agora: datetime.datetime,
) -> None:
    for ts in reordenados:
        _cancelar_preparo_pendente(db, ts.id, notif.MOTIVO_REORDENAR)
    _recalcular_e_reagendar(db, viagem, trip_students_ordenados, agora)


def processar_estou_atrasado(
    db: Session, viagem: Viagem, trip_students_ordenados: Sequence[TripStudent], minutos: int,
    agora: datetime.datetime,
) -> None:
    viagem.atraso_manual_segundos += minutos * 60
    _recalcular_e_reagendar(db, viagem, trip_students_ordenados, agora)
