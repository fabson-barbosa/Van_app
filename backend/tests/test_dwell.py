"""Testes unitários de dwell (Bloco B3, CLAUDE.md §5) — sem banco."""
import datetime

from app.services.dwell import calcular_dwell_segundos

T0 = datetime.datetime(2026, 7, 27, 7, 0, 0, tzinfo=datetime.timezone.utc)


def test_dwell_normal_e_a_diferenca_entre_checkin_e_chegou():
    chegou = T0
    checkin = T0 + datetime.timedelta(seconds=90)
    assert calcular_dwell_segundos(chegou, checkin) == 90.0


def test_dwell_aluno_ausente_direto_de_aguardando_e_none_nao_zero():
    # sem chegou_em (pulado) — CLAUDE.md §4: "não gravar dwell nem como zero"
    assert calcular_dwell_segundos(None, None) is None


def test_dwell_aluno_ainda_em_chegou_sem_checkin_e_none():
    # chegou mas ainda não fez checkin — dwell "em andamento", não é amostra ainda
    assert calcular_dwell_segundos(T0, None) is None
