"""Exceções de domínio da máquina de estados (Bloco B2).

Todas herdam de `DominioError` para que a camada de API possa capturar uma
única base e traduzir para HTTP, sem acoplar `services/` a FastAPI.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from app.models.trip_student import TripStudent, TripStudentEstado
    from app.models.viagem import ViagemStatus


class DominioError(Exception):
    """Base de toda exceção de regra de negócio da máquina de estados."""


class TransicaoInvalidaError(DominioError):
    """Ação não permitida a partir do estado atual do `trip_student`."""

    def __init__(self, estado_atual: "TripStudentEstado", acao: str) -> None:
        self.estado_atual = estado_atual
        self.acao = acao
        super().__init__(
            f"Transição inválida: aluno está em '{estado_atual.value}', ação '{acao}' não é permitida."
        )


class ParadaAnteriorPendenteError(DominioError):
    """CLAUDE.md §7.2 — bloqueia Cheguei(X) se houver parada anterior pendente
    (outro `trip_student` da mesma viagem, com ordem menor, ainda em `chegou`).
    """

    def __init__(self, pendentes: Sequence["TripStudent"]) -> None:
        self.pendentes = list(pendentes)
        ids = ", ".join(str(p.id) for p in self.pendentes)
        super().__init__(
            f"Existem alunos com parada anterior pendente (ainda em 'chegou'): {ids}. "
            "Resolva-os (Checkin ou Ausente) antes de confirmar esta chegada."
        )


class JanelaDesfazerExpiradaError(DominioError):
    """Desfazer checkin fora da janela de tolerância do servidor (60s)."""

    def __init__(self, janela_segundos: int, decorrido_segundos: float) -> None:
        self.janela_segundos = janela_segundos
        self.decorrido_segundos = decorrido_segundos
        super().__init__(
            f"Janela para desfazer checkin expirada: {decorrido_segundos:.0f}s decorridos, "
            f"limite é {janela_segundos}s."
        )


class ViagemStatusInvalidoError(DominioError):
    """A ação exige a viagem em um status diferente do atual."""

    def __init__(self, status_atual: "ViagemStatus", status_esperado: "ViagemStatus", acao: str) -> None:
        self.status_atual = status_atual
        self.status_esperado = status_esperado
        self.acao = acao
        super().__init__(
            f"Ação '{acao}' exige viagem em '{status_esperado.value}', "
            f"mas ela está em '{status_atual.value}'."
        )


class ReordenacaoInvalidaError(DominioError):
    """CLAUDE.md §8 — reordenar só é permitido enquanto o aluno está 'aguardando'
    (senão o trajeto seria atribuído ao par errado)."""

    def __init__(self, invalidos: Sequence["TripStudent"]) -> None:
        self.invalidos = list(invalidos)
        ids = ", ".join(str(t.id) for t in self.invalidos)
        super().__init__(
            f"Não é possível reordenar: alunos já passaram de 'aguardando': {ids}."
        )


class TripStudentDesconhecidoError(DominioError):
    """Um `trip_student_id` informado na reordenação não pertence à viagem."""

    def __init__(self, ids_desconhecidos: Sequence[uuid.UUID]) -> None:
        self.ids_desconhecidos = list(ids_desconhecidos)
        ids = ", ".join(str(i) for i in self.ids_desconhecidos)
        super().__init__(f"trip_student_id(s) não pertencem a esta viagem: {ids}.")


class VarreduraFinalPendenteError(DominioError):
    """CLAUDE.md §7.1 — regra inviolável: não finalizar com aluno em estado
    não terminal. `algum_a_bordo` sinaliza o caso mais grave (aluno esquecido
    a bordo), que exige alerta duro + notificação ao gestor."""

    def __init__(self, pendentes: Sequence["TripStudent"], algum_a_bordo: bool) -> None:
        self.pendentes = list(pendentes)
        self.algum_a_bordo = algum_a_bordo
        ids = ", ".join(str(p.id) for p in self.pendentes)
        aviso = " ALERTA: há aluno a bordo ao final da rota." if algum_a_bordo else ""
        super().__init__(
            f"Varredura final bloqueada: alunos em estado não terminal: {ids}.{aviso}"
        )
