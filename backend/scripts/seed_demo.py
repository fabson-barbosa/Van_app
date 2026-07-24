"""Seed de dados de demonstração — Sprint 1 (cadastros e multi-tenancy).

Cria um tenant fictício com um conjunto mínimo de dados coerente entre si
(rota -> parada -> aluno -> responsável), suficiente para demonstrar o CRUD
multi-tenant via Swagger (`/docs`) sem precisar digitar tudo manualmente.

Uso:
    cd backend
    python scripts/seed_demo.py

Idempotente: se o tenant de demo já existir (mesmo nome), o script aborta
sem duplicar dados — rode de novo só depois de limpar manualmente, se quiser
recriar do zero.
"""
import uuid

from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.aluno import Aluno, Responsavel
from app.models.rota import Parada, Rota
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.models.veiculo import Veiculo

TENANT_NOME = "Transportes Demo VaiVem"
ADMIN_EMAIL = "admin@demo.vaivem.com.br"
ADMIN_SENHA = "demo12345"  # só para ambiente de demonstração — nunca usar em produção


def seed(db: Session) -> None:
    existente = db.query(Tenant).filter(Tenant.nome == TENANT_NOME).first()
    if existente is not None:
        print(f"Tenant '{TENANT_NOME}' já existe (id={existente.id}). Nada a fazer.")
        return

    tenant = Tenant(id=uuid.uuid4(), nome=TENANT_NOME, plano="pro", status_billing="ativo")
    db.add(tenant)
    db.flush()

    # Tabelas com FORCE ROW LEVEL SECURITY (veiculos, rotas, alunos, consentimentos)
    # exigem `app.tenant_id` setado mesmo para o role `postgres` — mesmo mecanismo
    # usado por `get_tenant_db` em runtime (app/api/deps.py). `SET ... = :param`
    # não aceita bind parameters; `set_config` sim.
    db.execute(text("SELECT set_config('app.tenant_id', :tenant_id, false)"), {"tenant_id": str(tenant.id)})

    admin = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        nome="Admin Demo",
        email=ADMIN_EMAIL,
        senha_hash=hash_password(ADMIN_SENHA),
        role=UserRole.ADMIN,
        ativo=True,
    )
    db.add(admin)

    motorista = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        nome="Carlos Motorista",
        email="motorista@demo.vaivem.com.br",
        senha_hash=hash_password(ADMIN_SENHA),
        role=UserRole.MOTORISTA,
        ativo=True,
    )
    db.add(motorista)

    responsavel_user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        nome="Maria Responsável",
        email="responsavel@demo.vaivem.com.br",
        senha_hash=hash_password(ADMIN_SENHA),
        role=UserRole.RESPONSAVEL,
        ativo=True,
    )
    db.add(responsavel_user)

    veiculo = Veiculo(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        placa="ABC1D23",
        modelo="Fiat Ducato",
        capacidade=15,
        km_atual=42000,
    )
    db.add(veiculo)

    rota = Rota(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        nome="Rota Centro - Manhã",
        turno="manha",
        escola="Escola Municipal Pequeno Príncipe",
        ativa=True,
    )
    db.add(rota)
    db.flush()

    parada = Parada(
        id=uuid.uuid4(),
        rota_id=rota.id,
        nome="Praça Central",
        endereco="Praça Central, 100 - Centro",
        ordem_base=1,
        geo=from_shape(Point(-46.633308, -23.550520), srid=4326),  # São Paulo, lon/lat
    )
    db.add(parada)
    db.flush()

    aluno = Aluno(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        nome="João da Silva",
        parada_id=parada.id,
        dados_medicos=None,
        ativo=True,
    )
    db.add(aluno)
    db.flush()

    responsavel = Responsavel(
        id=uuid.uuid4(),
        aluno_id=aluno.id,
        user_id=responsavel_user.id,
        parentesco="mãe",
        permissoes={"ver_localizacao": True, "receber_notificacoes": True},
    )
    db.add(responsavel)

    db.commit()

    print("Seed concluído.")
    print(f"  tenant_id: {tenant.id}")
    print(f"  admin:       {ADMIN_EMAIL} / {ADMIN_SENHA}")
    print(f"  motorista:   motorista@demo.vaivem.com.br / {ADMIN_SENHA}")
    print(f"  responsável: responsavel@demo.vaivem.com.br / {ADMIN_SENHA}")


if __name__ == "__main__":
    session = SessionLocal()
    try:
        seed(session)
    finally:
        session.close()
