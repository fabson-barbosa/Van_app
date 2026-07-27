"""Simula uma viagem completa contra os dados do seed e imprime a timeline de
eventos + cada notificação que SERIA enviada (destinatário, instante,
conteúdo) — inclusive as canceladas (CLAUDE.md §5).

Uso:
    cd backend
    python scripts/seed_demo.py   # se ainda não rodou
    python scripts/simular_viagem.py

Cobre de propósito:
- uma casa pulada (`ausente` direto de `aguardando`) — mostra que nenhuma
  amostra de trajeto é gravada para o trecho que a atravessa (CLAUDE.md §4);
- um `desfazer_checkin` dentro da janela — mostra o cancelamento do aviso de
  `preparo` que aquele checkin tinha agendado (CLAUDE.md §5, gatilho crítico);
- um trecho propositalmente curto entre duas paradas, pra também exercitar
  o teto "preparo nunca depois do ETA da parada anterior".

Não usa push real (`StubFCMSender`) e roda tudo numa transação que é
DESFEITA no final (`rollback`) — não deixa lixo na base de demo; a viagem,
os trip_students e as notificações simuladas nunca são commitados.
"""
from __future__ import annotations

import datetime
import sys
import uuid

from sqlalchemy import select, text

from app.core.db import SessionLocal
from app.models.aluno import Aluno, Responsavel
from app.models.leg_duration import LegDuration
from app.models.motorista import Motorista
from app.models.notificacao import NotificacaoAgendada, NotificacaoEstado
from app.models.rota import Parada, Rota
from app.models.tenant import Tenant
from app.models.trip_student import TripStudent, TripStudentEstado
from app.models.veiculo import Veiculo
from app.models.viagem import Viagem, ViagemStatus
from app.services import pos_evento
from app.services import trip_state_machine as tsm
from app.services.notificacoes import StubFCMSender

TENANT_NOME = "Transportes Demo VaiVem"
T0 = datetime.datetime(2026, 7, 27, 7, 0, 0, tzinfo=datetime.timezone.utc)  # segunda-feira


def _fmt(dt: datetime.datetime) -> str:
    delta = dt - T0
    total = int(delta.total_seconds())
    sinal = "-" if total < 0 else "+"
    total = abs(total)
    return f"T{sinal}{total // 60:02d}:{total % 60:02d}"


def _payload_texto(tipo: str, payload: dict) -> str:
    if tipo == "chegada":
        return '"Chegamos, estamos esperando"'
    if tipo == "iminencia":
        return '"É a próxima!"'
    if tipo == "preparo":
        return f'"Faltam ~{payload.get("faixa_min_baixo")}-{payload.get("faixa_min_alto")} min"'
    return str(payload)


class _Narrador:
    """Imprime só o que MUDOU em `notificacoes_agendadas` desde a última
    checagem — snapshot simples por id, sem framework de diff."""

    def __init__(self, session, viagem_id, nomes_por_trip_student, nomes_por_user):
        self.session = session
        self.viagem_id = viagem_id
        self.nomes_ts = nomes_por_trip_student
        self.nomes_user = nomes_por_user
        self.visto: dict[uuid.UUID, tuple] = {}

    def evento(self, quando: datetime.datetime, titulo: str) -> None:
        print(f"\n[{_fmt(quando)}] {titulo}")

    def nota(self, texto: str) -> None:
        print(f"           {texto}")

    def diff_notificacoes(self) -> None:
        atuais = self.session.scalars(
            select(NotificacaoAgendada).where(NotificacaoAgendada.viagem_id == self.viagem_id)
        ).all()
        for n in atuais:
            chave = (n.estado, n.agendado_para, n.motivo_cancelamento)
            if self.visto.get(n.id) == chave:
                continue
            self.visto[n.id] = chave
            destinatario = self.nomes_user.get(n.destinatario_user_id, str(n.destinatario_user_id))
            alvo = self.nomes_ts.get(n.trip_student_id, str(n.trip_student_id))

            if n.estado == NotificacaoEstado.ENVIADO:
                texto = _payload_texto(n.tipo.value, n.payload)
                self.nota(f"notificação {n.tipo.value:<10} -> {destinatario:<24} ENVIADO   agora    {texto}")
            elif n.estado == NotificacaoEstado.AGENDADO:
                texto = _payload_texto(n.tipo.value, n.payload)
                self.nota(
                    f"notificação {n.tipo.value:<10} -> {destinatario:<24} AGENDADO  "
                    f"para {_fmt(n.agendado_para)} (sobre {alvo})  {texto}"
                )
            elif n.estado == NotificacaoEstado.CANCELADO:
                self.nota(
                    f"notificação {n.tipo.value:<10} -> {destinatario:<24} CANCELADO "
                    f'(sobre {alvo}) motivo="{n.motivo_cancelamento}"'
                )


def _leg_durations_snapshot(session, rota_id) -> dict:
    linhas = session.scalars(select(LegDuration).where(LegDuration.rota_id == rota_id)).all()
    return {(linha.ordem, linha.dia_semana, linha.faixa_horaria): linha.amostras for linha in linhas}


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # evita mojibake no console do Windows

    session = SessionLocal()
    try:
        _rodar(session)
    finally:
        session.rollback()  # nunca persiste — simulação, não seed
        session.close()


def _rodar(session) -> None:
    tenant = session.scalars(select(Tenant).where(Tenant.nome == TENANT_NOME)).first()
    if tenant is None:
        print(f'Tenant de demo "{TENANT_NOME}" não encontrado. Rode `python scripts/seed_demo.py` primeiro.')
        sys.exit(1)
    session.execute(text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": str(tenant.id)})

    rota = session.scalars(select(Rota).where(Rota.tenant_id == tenant.id).order_by(Rota.nome)).first()
    motorista = session.scalars(select(Motorista).where(Motorista.tenant_id == tenant.id)).first()
    veiculo = session.scalars(select(Veiculo).where(Veiculo.tenant_id == tenant.id)).first()

    alunos_paradas = list(
        session.execute(
            select(Aluno.id, Parada.id, Parada.ordem_base)
            .join(Parada, Aluno.parada_id == Parada.id)
            .where(Parada.rota_id == rota.id, Aluno.ativo.is_(True))
            .order_by(Parada.ordem_base)
        ).all()
    )
    if len(alunos_paradas) < 4:
        print(f'Rota "{rota.nome}" tem menos de 4 alunos — não dá pra simular casa pulada + desfazer checkin.')
        sys.exit(1)

    # Trecho propositalmente curto entre a 1ª e a 2ª parada, pra exercitar o
    # teto do preparo (CLAUDE.md §5) — as demais ficam com a semente padrão.
    parada2 = session.get(Parada, alunos_paradas[1][1])
    parada2.duracao_estimada_segundos = 150  # 2,5min — curto de propósito

    viagem = Viagem(
        id=uuid.uuid4(), tenant_id=tenant.id, rota_id=rota.id, veiculo_id=veiculo.id, motorista_id=motorista.id,
        data=T0.date(), status=ViagemStatus.PLANEJADA,
    )
    session.add(viagem)
    session.flush()

    novos = tsm.iniciar_viagem(viagem, alunos_paradas, now=T0)
    session.add_all(novos)
    session.flush()

    trip_students = sorted(
        session.scalars(select(TripStudent).where(TripStudent.viagem_id == viagem.id)), key=lambda ts: ts.ordem
    )
    alunos_por_id = {a.id: a for a in session.scalars(select(Aluno).where(Aluno.tenant_id == tenant.id)).all()}
    nomes_ts = {ts.id: alunos_por_id[ts.aluno_id].nome for ts in trip_students}
    responsaveis = session.scalars(
        select(Responsavel).where(Responsavel.aluno_id.in_([ts.aluno_id for ts in trip_students]))
    ).all()
    nomes_user = {r.user_id: f"Responsável de {alunos_por_id[r.aluno_id].nome.split()[0]}" for r in responsaveis}

    ordem_pulada = trip_students[2].ordem  # 3ª parada — casa pulada de propósito
    ordem_desfazer = trip_students[3].ordem  # 4ª parada — desfazer checkin de propósito

    sender = StubFCMSender()
    narrador = _Narrador(session, viagem.id, nomes_ts, nomes_user)

    print("=" * 78)
    print(f"Simulação — {rota.nome} ({len(trip_students)} alunos), tenant {tenant.nome}")
    print(f"Parada 1 -> 2 propositalmente curta (150s) para testar o teto do preparo.")
    print("=" * 78)
    narrador.evento(T0, f"Viagem iniciada às {T0.isoformat()}")

    agora = T0
    for i, ts in enumerate(trip_students):
        outros = trip_students  # já carregados, refletem mutações in-place

        if ts.ordem == ordem_pulada:
            agora = agora + datetime.timedelta(minutes=1)
            nome = nomes_ts[ts.id]
            narrador.evento(agora, f"AUSENTE  -> {nome} (casa pulada, direto de 'aguardando')")
            evento = tsm.registrar_ausente(viagem, ts, now=agora)
            session.add(evento)
            pos_evento.processar_ausente(session, viagem, outros, ts, agora)
            session.flush()
            narrador.diff_notificacoes()
            narrador.nota("(sem dwell gravado — CLAUDE.md §4: sem chegou_em, não há dwell nem como zero)")
            continue

        antes_leg = _leg_durations_snapshot(session, rota.id)

        agora = agora + datetime.timedelta(minutes=4)
        nome = nomes_ts[ts.id]
        narrador.evento(agora, f"CHEGUEI  -> {nome} (parada {ts.ordem})")
        evento = tsm.registrar_cheguei(viagem, ts, outros, now=agora)
        session.add(evento)
        pos_evento.processar_cheguei(session, viagem, outros, ts, agora, sender=sender)
        session.flush()
        narrador.diff_notificacoes()

        depois_leg = _leg_durations_snapshot(session, rota.id)
        if depois_leg == antes_leg:
            narrador.nota("(nenhuma amostra de trajeto gravada — parada anterior foi pulada)")
        else:
            narrador.nota("(amostra de trajeto gravada em leg_durations)")

        agora = agora + datetime.timedelta(seconds=30)
        narrador.evento(agora, f"CHECKIN  -> {nome}")
        evento = tsm.registrar_checkin(viagem, ts, now=agora)
        session.add(evento)
        pos_evento.processar_checkin(session, viagem, outros, ts, agora)
        session.flush()
        narrador.diff_notificacoes()

        if ts.ordem == ordem_desfazer:
            agora = agora + datetime.timedelta(seconds=20)
            narrador.evento(agora, f"DESFAZER CHECKIN -> {nome} (dentro da janela de 60s)")
            evento = tsm.desfazer_checkin(viagem, ts, now=agora)
            session.add(evento)
            pos_evento.processar_desfazer_checkin(session, viagem, outros, ts, agora)
            session.flush()
            narrador.diff_notificacoes()

            agora = agora + datetime.timedelta(seconds=20)
            narrador.evento(agora, f"CHECKIN  -> {nome} (de novo, válido)")
            evento = tsm.registrar_checkin(viagem, ts, now=agora)
            session.add(evento)
            pos_evento.processar_checkin(session, viagem, outros, ts, agora)
            session.flush()
            narrador.diff_notificacoes()

    agora = agora + datetime.timedelta(minutes=10)
    narrador.evento(agora, "Chegada na escola — checkout de todos os alunos a bordo")
    for ts in trip_students:
        if ts.estado == TripStudentEstado.A_BORDO:
            evento = tsm.registrar_checkout(viagem, ts, now=agora)
            session.add(evento)
            pos_evento.processar_checkout(session, viagem, trip_students, ts, agora)
    session.flush()
    narrador.diff_notificacoes()

    tsm.finalizar_viagem(viagem, trip_students, now=agora)
    session.flush()
    narrador.evento(agora, f"Viagem finalizada — varredura confirmada: {viagem.varredura_confirmada}")

    print("\n" + "=" * 78)
    print(f"atraso_acumulado_segundos (diagnóstico): {viagem.atraso_acumulado_segundos}")
    print(f"atraso_manual_segundos (nunca usado nesta simulação): {viagem.atraso_manual_segundos}")
    print(f"Notificações via StubFCMSender (imediatas): {len(sender.enviadas)}")
    print("Nada foi persistido — transação desfeita ao final (simulação, não seed).")
    print("=" * 78)


if __name__ == "__main__":
    main()
