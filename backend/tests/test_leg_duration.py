"""Testes unitários do motor de trajeto (Bloco B3, CLAUDE.md §5).

Sem banco — `leg_duration.py` é lógica pura (EWMA, validação de amostra,
agregação progressiva na leitura).
"""
from app.services.leg_duration import (
    BucketStats,
    escolher_estimativa,
    registrar_amostra,
    validar_amostra,
)


# ---------------------------------------------------------------------------
# validar_amostra — negativa/zero e outlier (> 3x referência)
# ---------------------------------------------------------------------------


def test_validar_amostra_rejeita_negativa():
    assert validar_amostra(-10, media_referencia=240) is False


def test_validar_amostra_rejeita_zero():
    assert validar_amostra(0, media_referencia=240) is False


def test_validar_amostra_rejeita_outlier_acima_de_3x():
    assert validar_amostra(721, media_referencia=240) is False  # 3x240=720, exclusive


def test_validar_amostra_aceita_exatamente_3x():
    assert validar_amostra(720, media_referencia=240) is True


def test_validar_amostra_aceita_valor_razoavel():
    assert validar_amostra(300, media_referencia=240) is True


# ---------------------------------------------------------------------------
# registrar_amostra — EWMA (alpha=0.3), semente como prior na 1ª amostra real
# ---------------------------------------------------------------------------


def test_registrar_amostra_primeira_usa_semente_como_prior():
    resultado = registrar_amostra(None, nova_amostra_segundos=300, estimativa_seed_segundos=240)
    assert resultado is not None
    # EWMA: 0.3*300 + 0.7*240 = 90 + 168 = 258
    assert resultado.segundos_media == 258.0
    assert resultado.amostras == 1


def test_registrar_amostra_seguinte_usa_bucket_existente_nao_semente():
    bucket = BucketStats(segundos_media=258.0, amostras=1)
    resultado = registrar_amostra(bucket, nova_amostra_segundos=300, estimativa_seed_segundos=999999)
    assert resultado is not None
    # EWMA: 0.3*300 + 0.7*258 = 90 + 180.6 = 270.6 — semente (999999) não entra mais
    assert resultado.segundos_media == 270.6
    assert resultado.amostras == 2


def test_registrar_amostra_descarta_negativa_nao_altera_bucket():
    bucket = BucketStats(segundos_media=258.0, amostras=1)
    resultado = registrar_amostra(bucket, nova_amostra_segundos=-5, estimativa_seed_segundos=240)
    assert resultado is None


def test_registrar_amostra_descarta_outlier_relogio_torto():
    # bucket com média 258s (~4.3min); amostra de 3000s (relógio torto num
    # evento offline) é > 3x a média — descarta.
    bucket = BucketStats(segundos_media=258.0, amostras=5)
    resultado = registrar_amostra(bucket, nova_amostra_segundos=3000, estimativa_seed_segundos=240)
    assert resultado is None


def test_registrar_amostra_primeira_amostra_tambem_valida_contra_a_semente():
    # sem bucket ainda, a semente é 240 — amostra de 1000s é outlier vs a semente
    resultado = registrar_amostra(None, nova_amostra_segundos=1000, estimativa_seed_segundos=240)
    assert resultado is None


# ---------------------------------------------------------------------------
# escolher_estimativa — agregação progressiva (CLAUDE.md §5)
# ---------------------------------------------------------------------------


def test_escolher_estimativa_usa_exato_com_5_ou_mais_amostras():
    exato = BucketStats(segundos_media=310.0, amostras=5)
    resultado = escolher_estimativa(
        exato=exato,
        agregado_dia=BucketStats(999.0, 100),
        agregado_geral=BucketStats(999.0, 100),
        estimativa_seed_segundos=240,
    )
    assert resultado == 310.0


def test_escolher_estimativa_cai_para_dia_quando_exato_tem_menos_de_5():
    exato = BucketStats(segundos_media=310.0, amostras=4)
    agregado_dia = BucketStats(segundos_media=280.0, amostras=5)
    resultado = escolher_estimativa(
        exato=exato, agregado_dia=agregado_dia, agregado_geral=BucketStats(999.0, 100),
        estimativa_seed_segundos=240,
    )
    assert resultado == 280.0


def test_escolher_estimativa_cai_para_geral_quando_dia_tem_menos_de_5():
    resultado = escolher_estimativa(
        exato=BucketStats(310.0, 2), agregado_dia=BucketStats(280.0, 3),
        agregado_geral=BucketStats(265.0, 8), estimativa_seed_segundos=240,
    )
    assert resultado == 265.0


def test_escolher_estimativa_cai_para_semente_quando_nao_ha_amostra_nenhuma():
    resultado = escolher_estimativa(
        exato=None, agregado_dia=BucketStats(0.0, 0), agregado_geral=BucketStats(0.0, 0),
        estimativa_seed_segundos=240,
    )
    assert resultado == 240


def test_escolher_estimativa_exato_none_nao_quebra():
    resultado = escolher_estimativa(
        exato=None, agregado_dia=BucketStats(280.0, 6), agregado_geral=BucketStats(0.0, 0),
        estimativa_seed_segundos=240,
    )
    assert resultado == 280.0
