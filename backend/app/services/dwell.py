"""Dwell — Checkin(N) - Cheguei(N), estatística SEPARADA de diagnóstico (CLAUDE.md §5).

Decisão tomada com o usuário: calculado SOB DEMANDA a partir de
`trip_students`, sem tabela nem média móvel própria — ao contrário de
`leg_duration.py` (trajeto), o CLAUDE.md não pede que dwell tenha memória
entre viagens, só que sirva de diagnóstico ("quais casas atrasam a rota").
Sem tabela nova, sem migration.
"""
from __future__ import annotations

import datetime


def calcular_dwell_segundos(
    chegou_em: datetime.datetime | None, checkin_em: datetime.datetime | None
) -> float | None:
    """`None` (nunca zero) se o aluno foi pulado (sem `chegou_em`) ou ainda
    não fez checkin — "dwell de aluno ausente não entra na média" (CLAUDE.md
    §4/§5); o chamador (uma futura query de diagnóstico) deve tratar `None`
    como "sem amostra", não como zero segundos de espera.
    """
    if chegou_em is None or checkin_em is None:
        return None
    return (checkin_em - chegou_em).total_seconds()
