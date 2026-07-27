"""Seed de dados de demonstração — Bloco B1 (CLAUDE.md §9).

Cria 1 tenant (operador) com 2 rotas e 12 alunos distribuídos entre elas
(6 cada), cada aluno com sua parada e seu responsável — dados coerentes o
bastante para exercitar RLS, RBAC e o motor de viagem dos blocos seguintes
via Swagger (`/docs`) sem digitar tudo manualmente.

Uso:
    cd backend
    python scripts/seed_demo.py

Idempotente: se o tenant de demo já existir (mesmo nome), o script aborta
sem duplicar dados — rode de novo só depois de limpar manualmente, se quiser
recriar do zero.

Fora de escopo deste seed (dados de execução, não de cadastro — ver B2/B3):
viagens, trip_students, eventos_aluno, leg_durations.
"""
import uuid

from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.aluno import Aluno, Responsavel
from app.models.motorista import Motorista
from app.models.rota import Parada, Rota
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.models.veiculo import Veiculo

TENANT_NOME = "Transportes Demo VaiVem"
ADMIN_EMAIL = "admin@demo.vaivem.com.br"
SENHA_DEMO = "demo12345"  # só para ambiente de demonstração — nunca usar em produção

# (nome da rota, escola, turno, placa do veículo, motorista, alunos)
ROTAS_DEMO = [
    {
        "nome": "Rota Centro - Manhã",
        "escola": "Escola Municipal Pequeno Príncipe",
        "turno": "manha",
        "veiculo_placa": "ABC1D23",
        "motorista_nome": "Carlos Motorista",
        "motorista_email": "motorista.centro@demo.vaivem.com.br",
        "motorista_cnh": "12345678900",
        "origem": (-46.633308, -23.550520),  # lon, lat — Praça da Sé, SP
        "alunos": [
            ("Sofia Almeida", "Praça Central, 100 - Centro"),
            ("Miguel Santos", "Rua das Flores, 220 - Centro"),
            ("Valentina Costa", "Av. Paulista, 900 - Centro"),
            ("Arthur Pereira", "Rua Augusta, 450 - Centro"),
            ("Helena Rodrigues", "Rua Direita, 78 - Centro"),
            ("Bernardo Lima", "Largo São Bento, 33 - Centro"),
        ],
    },
    {
        "nome": "Rota Jardim das Flores - Manhã",
        "escola": "Escola Municipal Pequeno Príncipe",
        "turno": "manha",
        "veiculo_placa": "XYZ9K87",
        "motorista_nome": "Ana Motorista",
        "motorista_email": "motorista.jardim@demo.vaivem.com.br",
        "motorista_cnh": "98765432100",
        "origem": (-46.656, -23.567),  # lon, lat — Jardins, SP
        "alunos": [
            ("Laura Oliveira", "Rua Jardim das Flores, 12"),
            ("Heitor Souza", "Rua Jardim das Flores, 45"),
            ("Manuela Ferreira", "Alameda Santos, 300"),
            ("Davi Carvalho", "Rua Oscar Freire, 500"),
            ("Alice Barbosa", "Rua Haddock Lobo, 210"),
            ("Théo Nascimento", "Alameda Lorena, 150"),
        ],
    },
]


def seed(db: Session) -> None:
    existente = db.query(Tenant).filter(Tenant.nome == TENANT_NOME).first()
    if existente is not None:
        print(f"Tenant '{TENANT_NOME}' já existe (id={existente.id}). Nada a fazer.")
        return

    tenant = Tenant(id=uuid.uuid4(), nome=TENANT_NOME, plano="pro", status_billing="ativo")
    db.add(tenant)
    db.flush()

    # Tabelas com FORCE ROW LEVEL SECURITY exigem `app.tenant_id` setado mesmo
    # para o role `postgres` — mesmo mecanismo usado por `get_tenant_db` em
    # runtime (app/api/deps.py). `SET ... = :param` não aceita bind
    # parameters; `set_config` sim.
    db.execute(text("SELECT set_config('app.tenant_id', :tenant_id, false)"), {"tenant_id": str(tenant.id)})

    admin = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        nome="Admin Demo",
        email=ADMIN_EMAIL,
        senha_hash=hash_password(SENHA_DEMO),
        role=UserRole.ADMIN,
        ativo=True,
    )
    db.add(admin)

    credenciais_impressas = [(admin.email, "admin")]

    for rota_spec in ROTAS_DEMO:
        motorista_user = User(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            nome=rota_spec["motorista_nome"],
            email=rota_spec["motorista_email"],
            senha_hash=hash_password(SENHA_DEMO),
            role=UserRole.MOTORISTA,
            ativo=True,
        )
        db.add(motorista_user)
        db.flush()

        motorista = Motorista(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            user_id=motorista_user.id,
            cnh_numero=rota_spec["motorista_cnh"],
            cnh_categoria="D",
            telefone="(11) 99999-0000",
            ativo=True,
        )
        db.add(motorista)

        veiculo = Veiculo(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            placa=rota_spec["veiculo_placa"],
            modelo="Fiat Ducato",
            capacidade=15,
            km_atual=42000,
        )
        db.add(veiculo)

        rota = Rota(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            nome=rota_spec["nome"],
            turno=rota_spec["turno"],
            escola=rota_spec["escola"],
            ativa=True,
        )
        db.add(rota)
        db.flush()

        lon0, lat0 = rota_spec["origem"]
        for i, (aluno_nome, endereco) in enumerate(rota_spec["alunos"], start=1):
            # Pequeno deslocamento por parada só para os pontos não colidirem no mapa.
            geo = from_shape(Point(lon0 + i * 0.001, lat0 + i * 0.001), srid=4326)
            parada = Parada(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                rota_id=rota.id,
                nome=f"Parada {i} - {aluno_nome.split()[0]}",
                endereco=endereco,
                ordem_base=i,
                geo=geo,
            )
            db.add(parada)
            db.flush()

            aluno = Aluno(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                nome=aluno_nome,
                parada_id=parada.id,
                dados_medicos=None,
                ativo=True,
            )
            db.add(aluno)
            db.flush()

            primeiro_nome = aluno_nome.split()[0]
            responsavel_email = f"responsavel.{primeiro_nome.lower()}@demo.vaivem.com.br"
            responsavel_user = User(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                nome=f"Responsável de {primeiro_nome}",
                email=responsavel_email,
                senha_hash=hash_password(SENHA_DEMO),
                role=UserRole.RESPONSAVEL,
                ativo=True,
            )
            db.add(responsavel_user)
            db.flush()

            responsavel = Responsavel(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                aluno_id=aluno.id,
                user_id=responsavel_user.id,
                parentesco="mãe" if i % 2 == 0 else "pai",
                permissoes={"ver_localizacao": True, "receber_notificacoes": True},
            )
            db.add(responsavel)

            credenciais_impressas.append((responsavel_email, "responsavel"))

        credenciais_impressas.append((rota_spec["motorista_email"], "motorista"))

    db.commit()

    print("Seed concluído.")
    print(f"  tenant_id: {tenant.id}")
    print(f"  senha (todos os usuários): {SENHA_DEMO}")
    print(f"  rotas: {len(ROTAS_DEMO)}")
    print(f"  alunos: {sum(len(r['alunos']) for r in ROTAS_DEMO)}")
    print("  usuários:")
    for email, papel in credenciais_impressas:
        print(f"    {papel:<12} {email}")


if __name__ == "__main__":
    session = SessionLocal()
    try:
        seed(session)
    finally:
        session.close()
