"""Motor de tempos — trajeto (Bloco B3, CLAUDE.md §5).

Lógica pura (sem sessão de banco, sem HTTP) — mesma filosofia de
`trip_state_machine.py`: recebe dados já carregados, devolve o que deveria
mudar; quem persiste é a camada fina em `app/services/pos_evento.py`.

Duas responsabilidades bem separadas:
1. `registrar_amostra` — atualiza UM bucket (`rota_id, ordem, dia_semana,
   faixa_horaria`) com uma amostra real de trajeto, via EWMA (média móvel
   exponencial, alpha=0.3 — decisão explícita: sem hiperparâmetro extra além
   do alpha, e a semente perde peso gradualmente em vez de sumir de uma vez).
   Rejeita amostras inválidas (negativas/zero, ou outliers > 3x a média de
   referência — relógio torto em evento offline gera lixo).
2. `escolher_estimativa` — agregação progressiva NA LEITURA (CLAUDE.md §5):
   sobe de granularidade conforme a amostragem permite. Escreve sempre na
   chave completa (`registrar_amostra` só mexe no bucket exato); a escolha de
   qual nível ler é decisão de query, não de schema — daí não ter migration
   nova para isso (a única migration nova do B3 é a tabela de notificações e
   as duas colunas de semente/atraso manual).

Semente ("estimativa do motorista"): vive em `Parada.duracao_estimada_segundos`
(nullable — `ESTIMATIVA_PADRAO_SEGUNDOS` cobre quando ninguém preencheu). NÃO
é gravada como uma linha de `leg_durations` — é usada só como o valor de
referência (`media_atual`) na primeira amostra real de um bucket que ainda não
existe, e como fallback final quando nenhum bucket do trecho tem amostra
nenhuma. Uma linha em `leg_durations` só nasce quando a 1ª amostra REAL chega.
"""
from __future__ import annotations

from dataclasses import dataclass

EWMA_ALPHA = 0.3
ESTIMATIVA_PADRAO_SEGUNDOS = 240  # 4min — usado quando Parada.duracao_estimada_segundos é nulo
MIN_AMOSTRAS_GRANULARIDADE = 5  # CLAUDE.md §5 — "só quando o balde tiver >= 5 amostras"


@dataclass(frozen=True)
class BucketStats:
    """Estado (existente ou agregado) de um ou mais buckets de `leg_durations`."""

    segundos_media: float
    amostras: int


def validar_amostra(segundos: float, media_referencia: float) -> bool:
    """Rejeita amostra negativa/zero ou outlier (> 3x a média de referência).

    `media_referencia` é o que a amostra seria comparada contra: a média do
    bucket exato se ele já existe, senão a semente (estimativa do motorista
    ou o padrão de 4min) — nunca comparamos contra zero.
    """
    if segundos <= 0:
        return False
    if media_referencia > 0 and segundos > 3 * media_referencia:
        return False
    return True


def registrar_amostra(
    bucket_atual: BucketStats | None,
    nova_amostra_segundos: float,
    estimativa_seed_segundos: float,
    *,
    alpha: float = EWMA_ALPHA,
) -> BucketStats | None:
    """Aplica uma amostra real de trajeto ao bucket exato.

    Retorna o novo `BucketStats` a persistir, ou `None` se a amostra foi
    descartada (inválida — chamador não deve escrever nada no banco).

    Se `bucket_atual` é `None` (1ª amostra real deste bucket), a semente
    entra como o valor "anterior" do EWMA — é isso que faz a semente
    perder peso gradualmente em vez de ser descartada de uma vez.
    """
    media_referencia = bucket_atual.segundos_media if bucket_atual is not None else estimativa_seed_segundos
    if not validar_amostra(nova_amostra_segundos, media_referencia):
        return None

    amostras_atuais = bucket_atual.amostras if bucket_atual is not None else 0
    nova_media = alpha * nova_amostra_segundos + (1 - alpha) * media_referencia
    return BucketStats(segundos_media=nova_media, amostras=amostras_atuais + 1)


def escolher_estimativa(
    *,
    exato: BucketStats | None,
    agregado_dia: BucketStats | None,
    agregado_geral: BucketStats | None,
    estimativa_seed_segundos: float,
) -> float:
    """Agregação progressiva (CLAUDE.md §5): dia+hora -> dia -> geral -> semente.

    `agregado_dia`/`agregado_geral` já vêm agregados (soma ponderada por
    amostras) pela camada de banco — esta função só decide qual nível usar,
    não faz SQL. `agregado_geral.amostras` reflete só amostras REAIS (nenhuma
    linha de `leg_durations` tem amostras=0 nesta versão — a semente nunca
    vira linha), então cair no `estimativa_seed_segundos` final significa
    literalmente "nenhuma amostra real existe em nenhum bucket deste trecho".
    """
    if exato is not None and exato.amostras >= MIN_AMOSTRAS_GRANULARIDADE:
        return exato.segundos_media
    if agregado_dia is not None and agregado_dia.amostras >= MIN_AMOSTRAS_GRANULARIDADE:
        return agregado_dia.segundos_media
    if agregado_geral is not None and agregado_geral.amostras > 0:
        return agregado_geral.segundos_media
    return estimativa_seed_segundos
