#!/usr/bin/env python3
"""Gera os 4 sons de confirmação do app Motorista (Bloco B8).

Rodar de `mobile/`:  python scripts/gerar_sons.py

Por que um gerador em vez de arquivos baixados: os WAVs são binários e
ninguém consegue revisar um binário num diff. Aqui o *desenho* do som fica
versionado — as notas, a duração, o envelope — e o arquivo é derivado.
Trocar um som é editar uma linha e rodar de novo.

Decisões acústicas, todas ditadas pelo ambiente (CLAUDE.md §8: o motorista
está dirigindo, o aparelho é antigo, a van é barulhenta):

- **Faixa de 700 Hz a 1,4 kHz.** Alto-falante de celular antigo praticamente
  não reproduz graves, e o ruído de motor/rua mora embaixo de 500 Hz. Um
  "buzz" grave de erro — o reflexo óbvio — seria justamente o que não se
  ouve dentro da van.
- **Curtos (≤ 320 ms).** É confirmação, não notificação. Som que se arrasta
  vira ruído e o motorista desliga o recurso.
- **Direção do intervalo carrega o significado**: subir = registrado, descer
  = encerrado, glissando descendente = revertido, dissonância = recusado.
  O motorista sabe QUAL comando apertou; o som precisa dizer se entrou e em
  que categoria — sem exigir que ele olhe a tela.
- **Envelope com ataque e queda de 6 ms** em cada segmento: corte seco em
  onda cheia estala no alto-falante, e um clique é indistinguível de defeito.
"""
import math
import pathlib
import struct
import wave

TAXA = 44100
AMPLITUDE = 0.55  # deixa headroom — clipping em alto-falante pequeno distorce
RAMPA_S = 0.006

DESTINO = pathlib.Path(__file__).resolve().parent.parent / "assets" / "sons"


def _envelope(indice: int, total: int) -> float:
    """Ataque/queda lineares curtos, platô no meio."""
    rampa = max(1, int(RAMPA_S * TAXA))
    if indice < rampa:
        return indice / rampa
    if indice > total - rampa:
        return max(0.0, (total - indice) / rampa)
    return 1.0


def tom(freq_inicial: float, duracao_s: float, freq_final: float | None = None,
        harmonico2: float = 0.0) -> list[float]:
    """Um segmento senoidal, opcionalmente com glissando e 2º harmônico.

    O 2º harmônico dá "corpo" sem sujar o timbre — um seno puro soa fino e
    some no ruído; onda quadrada soa como alarme de defeito.
    """
    total = int(duracao_s * TAXA)
    destino = freq_inicial if freq_final is None else freq_final
    amostras: list[float] = []
    fase = 0.0
    for i in range(total):
        # Interpola a frequência (glissando) integrando a fase, não
        # recalculando sin(2*pi*f*t): variar f dentro de sin() com t absoluto
        # produz salto de fase audível como estalo no meio do glissando.
        freq = freq_inicial + (destino - freq_inicial) * (i / max(1, total - 1))
        fase += 2 * math.pi * freq / TAXA
        valor = math.sin(fase) + harmonico2 * math.sin(2 * fase)
        amostras.append(valor / (1 + harmonico2) * _envelope(i, total))
    return amostras


def silencio(duracao_s: float) -> list[float]:
    return [0.0] * int(duracao_s * TAXA)


def mistura(*camadas: list[float]) -> list[float]:
    """Soma segmentos de mesmo tamanho (para dissonância simultânea)."""
    tamanho = max(len(c) for c in camadas)
    saida = [0.0] * tamanho
    for camada in camadas:
        for i, v in enumerate(camada):
            saida[i] += v
    return [v / len(camadas) for v in saida]


def escrever(nome: str, amostras: list[float]) -> None:
    DESTINO.mkdir(parents=True, exist_ok=True)
    caminho = DESTINO / nome
    with wave.open(str(caminho), "wb") as arquivo:
        arquivo.setnchannels(1)
        arquivo.setsampwidth(2)
        arquivo.setframerate(TAXA)
        quadros = b"".join(
            struct.pack("<h", int(max(-1.0, min(1.0, v * AMPLITUDE)) * 32767))
            for v in amostras
        )
        arquivo.writeframes(quadros)
    ms = len(amostras) / TAXA * 1000
    print(f"  {nome:16s} {ms:5.0f} ms  {caminho.stat().st_size / 1024:5.1f} KB")


def main() -> None:
    print("Gerando sons de feedback do Motorista em assets/sons/")

    # ACEITO — comando registrado (Cheguei, Checkin). Duas notas SUBINDO:
    # B5 -> E6. Intervalo aberto (quarta justa), soa inequivocamente positivo.
    escrever("aceito.wav", tom(988, 0.075, harmonico2=0.25) + tom(1319, 0.095, harmonico2=0.25))

    # CONCLUIDO — ação terminal (Checkout, Ausente, Finalizar viagem). Três
    # notas DESCENDO até a tônica: E6 -> C6 -> G5. Cadência resolvida = "fechou,
    # não tem volta" — que é literalmente o que esses estados significam na
    # máquina de estados (§4: `entregue`/`ausente` são terminais).
    escrever(
        "concluido.wav",
        tom(1319, 0.065, harmonico2=0.2) + tom(1047, 0.065, harmonico2=0.2) + tom(784, 0.13, harmonico2=0.3),
    )

    # ERRO — recusa: 409 de domínio, bloqueio do §7.2, falha definitiva. Duas
    # notas SIMULTÂNEAS a um semitom (Bb5 + B5) = dissonância crua, batimento
    # audível. Repetida em dois pulsos curtos, padrão que não existe em nenhum
    # dos sons de sucesso. Fica na mesma faixa audível dos outros de propósito:
    # erro é a informação que MAIS precisa atravessar o ruído da van.
    pulso = mistura(tom(932, 0.085), tom(988, 0.085))
    escrever("erro.wav", pulso + silencio(0.055) + pulso)

    # DESFEITO — undo do checkin, desfazer chegada. Glissando DESCENDENTE
    # contínuo (E6 -> F#5): "voltou atrás". Contínuo em vez de duas notas
    # discretas para não ser confundido com `concluido`, que também desce.
    escrever("desfeito.wav", tom(1319, 0.16, freq_final=740, harmonico2=0.15))

    print("Pronto.")


if __name__ == "__main__":
    main()
