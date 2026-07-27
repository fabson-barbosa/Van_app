"""Teste de integração obrigatório (Bloco B4, aprovado pelo usuário antes da
implementação): um lote de eventos sincronizado de uma vez, depois que o app
do Motorista ficou offline, precisa produzir EXATAMENTE os mesmos
`leg_durations` que os mesmos eventos enviados ao vivo — é a prova de que a
reconciliação de relógio (`app/services/reconciliacao.py`) preserva os
intervalos reais em vez de colapsá-los para perto de zero quando o servidor
recebe tudo de uma vez.

Cenário: dois tenants/rotas idênticos (mesma estrutura de 4 paradas, mesmos
6 eventos — 3 pares Cheguei/Checkin), rodados com relógios diferentes:

- "ao vivo": cada evento chega ao servidor no instante em que realmente
  aconteceu (`device_enviado_em` == `agora_servidor` == instante real,
  offset = 0).
- "em lote": o aparelho tem uma deriva REAL de +3min (não é só o atraso da
  fila — o relógio dele está errado) e os 6 eventos só chegam ao servidor
  juntos, na reconexão, muito depois de terem ocorrido de verdade.

A reconciliação precisa cancelar as duas coisas (deriva do aparelho + atraso
de sincronização) e recuperar o MESMO `ocorrido_em` que o cenário ao vivo —
por isso os buckets de `leg_durations` resultantes têm que bater, amostra a
amostra.
"""
import datetime
import uuid

import pytest
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import select

from app.core.security import hash_password
from app.models.aluno import Aluno
from app.models.leg_duration import LegDuration
from app.models.motorista import Motorista
from app.models.rota import Parada, Rota
from app.models.tenant import Tenant
from app.models.trip_student import TripStudent
from app.models.user import User, UserRole
from app.models.veiculo import Veiculo
from app.models.viagem import Viagem, ViagemStatus
from app.services import pos_evento
from app.services import trip_state_machine as tsm
from app.services.reconciliacao import reconciliar
from tests.integration.conftest import set_tenant

pytestmark = pytest.mark.integration

T0 = datetime.datetime(2026, 7, 27, 7, 0, 0, tzinfo=datetime.timezone.utc)  # segunda-feira
DERIVA_APARELHO = datetime.timedelta(minutes=3)


def _dt(segundos: int) -> datetime.datetime:
    return T0 + datetime.timedelta(seconds=segundos)


def _criar_cenario(session, sufixo: str, n_paradas: int = 4):
    tenant = Tenant(id=uuid.uuid4(), nome=f"Tenant Lote {sufixo} {uuid.uuid4()}", plano="pro", status_billing="ativo")
    session.add(tenant)
    session.flush()
    set_tenant(session, tenant.id)

    motorista_user = User(
        id=uuid.uuid4(), tenant_id=tenant.id, nome="Motorista", email=f"m.{sufixo}.{uuid.uuid4()}@teste.com",
        senha_hash=hash_password("x"), role=UserRole.MOTORISTA, ativo=True,
    )
    session.add(motorista_user)
    session.flush()
    motorista = Motorista(id=uuid.uuid4(), tenant_id=tenant.id, user_id=motorista_user.id, ativo=True)
    session.add(motorista)
    veiculo = Veiculo(id=uuid.uuid4(), tenant_id=tenant.id, placa=f"LT{sufixo[:5].upper()}", km_atual=0)
    session.add(veiculo)
    rota = Rota(id=uuid.uuid4(), tenant_id=tenant.id, nome=f"Rota Lote {sufixo}", turno="manha", ativa=True)
    session.add(rota)
    session.flush()

    alunos_paradas = []
    for i in range(1, n_paradas + 1):
        parada = Parada(
            id=uuid.uuid4(), tenant_id=tenant.id, rota_id=rota.id, nome=f"Parada {i}", ordem_base=i,
            geo=from_shape(Point(-46.6 + i * 0.001, -23.5), srid=4326),
        )
        session.add(parada)
        session.flush()
        aluno = Aluno(id=uuid.uuid4(), tenant_id=tenant.id, nome=f"Aluno {i}", parada_id=parada.id, ativo=True)
        session.add(aluno)
        session.flush()
        alunos_paradas.append((aluno.id, parada.id, i))

    viagem = Viagem(
        id=uuid.uuid4(), tenant_id=tenant.id, rota_id=rota.id, veiculo_id=veiculo.id, motorista_id=motorista.id,
        data=T0.date(), status=ViagemStatus.PLANEJADA,
    )
    session.add(viagem)
    session.flush()
    novos = tsm.iniciar_viagem(viagem, alunos_paradas, ocorrido_em=T0)
    session.add_all(novos)
    session.commit()

    trip_students = sorted(
        session.scalars(select(TripStudent).where(TripStudent.viagem_id == viagem.id)), key=lambda ts: ts.ordem
    )
    return {"tenant_id": tenant.id, "rota_id": rota.id, "viagem": viagem, "trip_students": trip_students}


def _processar(session, viagem, trip_students, alvo, tipo, *, device_timestamp, device_enviado_em, agora_servidor):
    reconciliado = reconciliar(
        device_timestamp=device_timestamp, device_enviado_em=device_enviado_em,
        agora_servidor=agora_servidor, nao_antes_de=viagem.iniciada_em,
    )
    if tipo == "cheguei":
        evento = tsm.registrar_cheguei(
            viagem, alvo, trip_students, ocorrido_em=reconciliado.ocorrido_em, registrado_em=agora_servidor,
            device_timestamp=device_timestamp,
        )
        session.add(evento)
        pos_evento.processar_cheguei(
            session, viagem, trip_students, alvo, evento.ocorrido_em, registrar_amostra=reconciliado.confiavel
        )
    elif tipo == "checkin":
        evento = tsm.registrar_checkin(
            viagem, alvo, ocorrido_em=reconciliado.ocorrido_em, registrado_em=agora_servidor,
            device_timestamp=device_timestamp,
        )
        session.add(evento)
        pos_evento.processar_checkin(session, viagem, trip_students, alvo, evento.ocorrido_em)
    else:
        raise ValueError(tipo)
    session.commit()
    return reconciliado


def _rodar_sequencia(session, cenario, *, offline: bool):
    """3 pares Cheguei/Checkin (6 eventos) nos 3 primeiros alunos da rota —
    cada Cheguei(N) usa o Checkin(N-1) como âncora, então há 3 amostras de
    trajeto encadeadas. `T_i` são os instantes REAIS de ocorrência, idênticos
    nos dois cenários; só o relógio/momento de envio muda."""
    viagem, trip_students = cenario["viagem"], cenario["trip_students"]
    ocorrencias_reais = [
        ("cheguei", trip_students[0], _dt(240)),
        ("checkin", trip_students[0], _dt(270)),
        ("cheguei", trip_students[1], _dt(600)),
        ("checkin", trip_students[1], _dt(630)),
        ("cheguei", trip_students[2], _dt(900)),
        ("checkin", trip_students[2], _dt(930)),
    ]

    if not offline:
        for tipo, alvo, t_real in ocorrencias_reais:
            _processar(
                session, viagem, trip_students, alvo, tipo,
                device_timestamp=t_real, device_enviado_em=t_real, agora_servidor=t_real,
            )
        return

    # Offline: aparelho com deriva real de +3min, todos os 6 eventos só
    # chegam ao servidor juntos, na reconexão — bem depois da última
    # ocorrência real (_dt(930)).
    t_sync_real = _dt(930) + datetime.timedelta(minutes=45)
    device_enviado_em = t_sync_real + DERIVA_APARELHO
    for tipo, alvo, t_real in ocorrencias_reais:
        device_timestamp = t_real + DERIVA_APARELHO
        _processar(
            session, viagem, trip_students, alvo, tipo,
            device_timestamp=device_timestamp, device_enviado_em=device_enviado_em, agora_servidor=t_sync_real,
        )


def _leg_durations_por_ordem(session, rota_id) -> dict:
    linhas = session.scalars(select(LegDuration).where(LegDuration.rota_id == rota_id)).all()
    return {l.ordem: (round(l.segundos_media, 6), l.amostras, l.dia_semana, l.faixa_horaria) for l in linhas}


def test_lote_offline_produz_mesmos_leg_durations_que_ao_vivo(db_session):
    cenario_ao_vivo = _criar_cenario(db_session, "vivo")
    set_tenant(db_session, cenario_ao_vivo["tenant_id"])
    _rodar_sequencia(db_session, cenario_ao_vivo, offline=False)

    cenario_lote = _criar_cenario(db_session, "lote")
    set_tenant(db_session, cenario_lote["tenant_id"])
    _rodar_sequencia(db_session, cenario_lote, offline=True)

    buckets_ao_vivo = _leg_durations_por_ordem(db_session, cenario_ao_vivo["rota_id"])
    buckets_lote = _leg_durations_por_ordem(db_session, cenario_lote["rota_id"])

    assert len(buckets_ao_vivo) == 3, "esperava 3 amostras de trajeto (ordens 1, 2, 3 — uma por Cheguei)"
    assert buckets_ao_vivo == buckets_lote, (
        "reconciliação deveria cancelar deriva do aparelho + atraso de sincronização "
        "e produzir os MESMOS buckets que o cenário ao vivo"
    )


def test_lote_offline_com_offset_alem_do_clamp_nao_grava_amostra_contaminada(db_session):
    """Se o offset implícito estourar `OFFSET_MAXIMO` (ex.: `device_enviado_em`
    ausente/absurdo), a reconciliação cai em `agora_servidor` com
    `confiavel=False` — `processar_cheguei` não deve gravar amostra nenhuma
    (contaminaria o EWMA com um instante que não é medida real)."""
    cenario = _criar_cenario(db_session, "clamp")
    viagem, trip_students = cenario["viagem"], cenario["trip_students"]
    set_tenant(db_session, cenario["tenant_id"])
    alvo = trip_students[0]

    agora_servidor = _dt(1000)
    reconciliado = reconciliar(
        device_timestamp=None, device_enviado_em=None, agora_servidor=agora_servidor,
        nao_antes_de=viagem.iniciada_em,
    )
    assert reconciliado.confiavel is False

    evento = tsm.registrar_cheguei(
        viagem, alvo, trip_students, ocorrido_em=reconciliado.ocorrido_em, registrado_em=agora_servidor,
    )
    db_session.add(evento)
    pos_evento.processar_cheguei(
        db_session, viagem, trip_students, alvo, evento.ocorrido_em, registrar_amostra=reconciliado.confiavel
    )
    db_session.commit()

    assert _leg_durations_por_ordem(db_session, cenario["rota_id"]) == {}
