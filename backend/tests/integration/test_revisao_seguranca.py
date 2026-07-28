"""Testes de integração da revisão de segurança pós-B5 (Postgres real).

Rodar com `pytest -m integration`. Cobrem os achados que dependem de banco:
- §11 — reatribuição de viagem (`POST /api/viagens/{id}/reatribuir`): admin
  realoca; `motorista_backup` só assume para si e só em andamento; auditoria
  em `viagem_reatribuicoes` (append-only).
- A3 — soft-delete: `remover_aluno` marca `ativo=False` (não hard-delete) e o
  aluno some das listagens.

Chamam as funções do router diretamente (mesmo padrão dos demais testes de
integração), passando `db`/`user` no lugar dos `Depends(...)`.
"""
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.api.alunos import listar_alunos, remover_aluno
from app.api.viagens import reatribuir_viagem
from app.core.security import hash_password
from app.models.aluno import Aluno, Responsavel
from app.models.motorista import Motorista
from app.models.user import User, UserRole
from app.models.viagem import ViagemStatus
from app.models.viagem_reatribuicao import ViagemReatribuicao
from app.schemas.auth import CurrentUser
from app.schemas.viagens import ReatribuirViagemRequest
from tests.integration.conftest import set_tenant
from tests.integration.test_notificacoes_agendamento import _criar_cenario

pytestmark = pytest.mark.integration


def _admin_user(db, tenant_id) -> CurrentUser:
    """Cria uma linha real de admin (o FK `reatribuido_por_user_id` exige que
    o ator exista) e devolve o CurrentUser correspondente."""
    row = User(
        id=uuid.uuid4(), tenant_id=tenant_id, nome="Admin Teste",
        email=f"admin.{uuid.uuid4()}@teste.com", senha_hash=hash_password("x"),
        role=UserRole.ADMIN, ativo=True,
    )
    db.add(row)
    db.commit()
    return CurrentUser(id=row.id, tenant_id=tenant_id, email=row.email, role=UserRole.ADMIN)


def _criar_backup(db, tenant_id) -> tuple[Motorista, CurrentUser]:
    user = User(
        id=uuid.uuid4(), tenant_id=tenant_id, nome="Bruno Backup",
        email=f"backup.{uuid.uuid4()}@teste.com", senha_hash=hash_password("x"),
        role=UserRole.MOTORISTA_BACKUP, ativo=True,
    )
    db.add(user)
    db.flush()
    motorista = Motorista(id=uuid.uuid4(), tenant_id=tenant_id, user_id=user.id, ativo=True)
    db.add(motorista)
    db.commit()
    cu = CurrentUser(id=user.id, tenant_id=tenant_id, email=user.email, role=UserRole.MOTORISTA_BACKUP)
    return motorista, cu


# ---------------------------------------------------------------------------
# §11 — reatribuição
# ---------------------------------------------------------------------------


def test_admin_reatribui_e_grava_auditoria(db_session):
    cenario = _criar_cenario(db_session, n_paradas=2)
    tenant_id = cenario["tenant_id"]
    set_tenant(db_session, tenant_id)
    viagem = cenario["viagem"]
    titular_id = viagem.motorista_id
    admin = _admin_user(db_session, tenant_id)
    backup_motorista, _ = _criar_backup(db_session, tenant_id)

    out = reatribuir_viagem(
        viagem.id, ReatribuirViagemRequest(motorista_id=backup_motorista.id, motivo="titular sem sinal"),
        db=db_session, user=admin,
    )

    assert out.motorista_id == backup_motorista.id
    regs = db_session.scalars(
        select(ViagemReatribuicao).where(ViagemReatribuicao.viagem_id == viagem.id)
    ).all()
    assert len(regs) == 1
    assert regs[0].motorista_anterior_id == titular_id
    assert regs[0].motorista_novo_id == backup_motorista.id
    assert regs[0].reatribuido_por_user_id == admin.id


def test_backup_assume_para_si_viagem_em_andamento(db_session):
    cenario = _criar_cenario(db_session, n_paradas=2)
    tenant_id = cenario["tenant_id"]
    set_tenant(db_session, tenant_id)
    viagem = cenario["viagem"]  # _criar_cenario já inicia (em_andamento)
    backup_motorista, backup_cu = _criar_backup(db_session, tenant_id)

    out = reatribuir_viagem(
        viagem.id, ReatribuirViagemRequest(motorista_id=backup_motorista.id),
        db=db_session, user=backup_cu,
    )
    assert out.motorista_id == backup_motorista.id


def test_backup_nao_pode_reatribuir_para_terceiro(db_session):
    cenario = _criar_cenario(db_session, n_paradas=2)
    tenant_id = cenario["tenant_id"]
    set_tenant(db_session, tenant_id)
    viagem = cenario["viagem"]
    titular_id = viagem.motorista_id  # um "terceiro" do ponto de vista do backup
    _, backup_cu = _criar_backup(db_session, tenant_id)

    with pytest.raises(HTTPException) as exc:
        reatribuir_viagem(
            viagem.id, ReatribuirViagemRequest(motorista_id=titular_id),
            db=db_session, user=backup_cu,
        )
    assert exc.value.status_code == 403


def test_backup_nao_assume_viagem_planejada(db_session):
    cenario = _criar_cenario(db_session, n_paradas=2)
    tenant_id = cenario["tenant_id"]
    set_tenant(db_session, tenant_id)
    viagem = cenario["viagem"]
    viagem.status = ViagemStatus.PLANEJADA
    db_session.commit()
    backup_motorista, backup_cu = _criar_backup(db_session, tenant_id)

    with pytest.raises(HTTPException) as exc:
        reatribuir_viagem(
            viagem.id, ReatribuirViagemRequest(motorista_id=backup_motorista.id),
            db=db_session, user=backup_cu,
        )
    assert exc.value.status_code == 403


def test_auditoria_reatribuicao_e_append_only(db_session):
    """O trigger de imutabilidade (migration 0010) bloqueia UPDATE/DELETE na
    trilha de auditoria, mesma garantia de `eventos_aluno` (§7.4)."""
    from sqlalchemy import text
    from sqlalchemy.exc import InternalError, ProgrammingError

    cenario = _criar_cenario(db_session, n_paradas=1)
    tenant_id = cenario["tenant_id"]
    set_tenant(db_session, tenant_id)
    viagem = cenario["viagem"]
    admin = _admin_user(db_session, tenant_id)
    backup_motorista, _ = _criar_backup(db_session, tenant_id)
    reatribuir_viagem(
        viagem.id, ReatribuirViagemRequest(motorista_id=backup_motorista.id),
        db=db_session, user=admin,
    )
    reg = db_session.scalars(
        select(ViagemReatribuicao).where(ViagemReatribuicao.viagem_id == viagem.id)
    ).first()

    with pytest.raises((InternalError, ProgrammingError)):
        db_session.execute(
            text("UPDATE viagem_reatribuicoes SET motivo = 'x' WHERE id = :i"), {"i": str(reg.id)}
        )
        db_session.flush()
    db_session.rollback()
    set_tenant(db_session, tenant_id)

    with pytest.raises((InternalError, ProgrammingError)):
        db_session.execute(text("DELETE FROM viagem_reatribuicoes WHERE id = :i"), {"i": str(reg.id)})
        db_session.flush()
    db_session.rollback()


# ---------------------------------------------------------------------------
# A3 — soft-delete
# ---------------------------------------------------------------------------


def test_remover_aluno_faz_soft_delete_e_some_da_listagem(db_session):
    cenario = _criar_cenario(db_session, n_paradas=2)
    tenant_id = cenario["tenant_id"]
    set_tenant(db_session, tenant_id)
    admin = _admin_user(db_session, tenant_id)
    alvo_aluno_id = cenario["trip_students"][0].aluno_id

    antes = {a.id for a in listar_alunos(db=db_session, _user=admin)}
    assert alvo_aluno_id in antes

    remover_aluno(aluno_id=alvo_aluno_id, db=db_session, _user=admin)

    # A linha continua existindo (não foi hard-deleted), só inativa.
    persistida = db_session.get(Aluno, alvo_aluno_id)
    assert persistida is not None
    assert persistida.ativo is False
    # E seus responsáveis também foram desativados em cascata na aplicação.
    resp = db_session.scalars(
        select(Responsavel).where(Responsavel.aluno_id == alvo_aluno_id)
    ).all()
    assert resp and all(r.ativo is False for r in resp)
    # Some da listagem.
    depois = {a.id for a in listar_alunos(db=db_session, _user=admin)}
    assert alvo_aluno_id not in depois
