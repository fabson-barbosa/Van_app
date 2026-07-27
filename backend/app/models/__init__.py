"""Models SQLAlchemy — tabelas-núcleo da Fase 1 (ver docs/planejamento/arquitetura.md, seção 5)
e do Bloco B1 (CLAUDE.md, seção 9): motorista, viagem, trip_student, evento_aluno, leg_duration.

Importar todos os models aqui garante que o Alembic os enxergue via Base.metadata
ao autogerar migrations.
"""
from app.models.aluno import Aluno, Responsavel
from app.models.consentimento import Consentimento
from app.models.evento_aluno import EventoAluno, EventoAlunoTipo
from app.models.leg_duration import LegDuration
from app.models.motorista import Motorista
from app.models.notificacao import NotificacaoAgendada, NotificacaoEstado, NotificacaoTipo
from app.models.rota import Parada, Rota
from app.models.tenant import Tenant
from app.models.trip_student import TripStudent, TripStudentEstado
from app.models.user import User, UserRole
from app.models.veiculo import Veiculo
from app.models.viagem import Viagem, ViagemStatus

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
    "Motorista",
    "Viagem",
    "ViagemStatus",
    "TripStudent",
    "TripStudentEstado",
    "EventoAluno",
    "EventoAlunoTipo",
    "LegDuration",
    "NotificacaoAgendada",
    "NotificacaoTipo",
    "NotificacaoEstado",
]
