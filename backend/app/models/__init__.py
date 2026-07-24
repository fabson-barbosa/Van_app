"""Models SQLAlchemy — tabelas-núcleo da Fase 1 (ver docs/planejamento/arquitetura.md, seção 5).

Importar todos os models aqui garante que o Alembic os enxergue via Base.metadata
ao autogerar migrations.
"""
from app.models.aluno import Aluno, Responsavel
from app.models.consentimento import Consentimento
from app.models.rota import Parada, Rota
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.models.veiculo import Veiculo

__all__ = [
    "Tenant",
    "User",
    "UserRole",
    "Veiculo",
    "Rota",
    "Parada",
    "Aluno",
    "Responsavel",
    "Consentimento",
]
