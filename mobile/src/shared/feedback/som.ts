/**
 * Sons de confirmação do app Motorista (Bloco B8).
 *
 * O háptico do B7 resolveu metade do problema do CLAUDE.md §8 ("confirmação só
 * visual obriga o motorista a olhar a tela"). A outra metade é que o aparelho
 * fica no suporte do painel, não na mão — vibração num suporte de plástico não
 * chega ao motorista. Som chega.
 *
 * Quatro amostras, geradas por `scripts/gerar_sons.py` (o desenho acústico está
 * documentado lá): `aceito`, `concluido`, `erro`, `desfeito`.
 *
 * Decisões:
 *
 * - **`duckOthers`.** A van costuma estar com rádio ou navegação tocando. Pausar
 *   o áudio de outro app (`doNotMix`) para um blip de 170ms é agressivo e deixa
 *   a música engasgando a cada casa; `mixWithOthers` não pede foco nenhum e o
 *   som sumiria embaixo da música — justamente o que ele existe para evitar.
 *   Abaixar o volume dos outros por um instante é o único que cumpre os dois.
 * - **Nunca lança.** Aparelho sem áudio, volume zero, módulo nativo que não
 *   carregou no Expo Go: falha silenciosa. Nenhum fluxo pode depender disto —
 *   é reforço, igual ao háptico. O canal de verdade continua sendo a tela.
 * - **Players criados na primeira vez que cada som toca**, e reaproveitados. Os
 *   quatro juntos são ~70KB; instanciar no import atrasaria o start do app em
 *   aparelho antigo por um recurso que talvez nem seja usado na sessão.
 * - **`seekTo(0)` antes de tocar.** Sem isso, o segundo toque no mesmo som não
 *   emite nada: o player está parado no fim da amostra.
 */
import AsyncStorage from "@react-native-async-storage/async-storage";
import { type AudioPlayer, createAudioPlayer, setAudioModeAsync } from "expo-audio";

export type NomeSom = "aceito" | "concluido" | "erro" | "desfeito";

export const CHAVE_SOM = "vaivem.som.ligado";

/* eslint-disable @typescript-eslint/no-require-imports */
const FONTES: Record<NomeSom, unknown> = {
  aceito: require("../../../assets/sons/aceito.wav"),
  concluido: require("../../../assets/sons/concluido.wav"),
  erro: require("../../../assets/sons/erro.wav"),
  desfeito: require("../../../assets/sons/desfeito.wav"),
};
/* eslint-enable @typescript-eslint/no-require-imports */

const players = new Map<NomeSom, AudioPlayer | null>();

let ligado = true;
let modoConfigurado = false;
const ouvintes = new Set<(ligado: boolean) => void>();

/** Preferência em vigor. Síncrono de propósito: os pontos de chamada estão em
 * handlers de toque, e um `await` aqui atrasaria o som do próprio toque. */
export function somLigado(): boolean {
  return ligado;
}

export function assinarSom(ouvinte: (ligado: boolean) => void): () => void {
  ouvintes.add(ouvinte);
  return () => ouvintes.delete(ouvinte);
}

export function definirSom(novo: boolean): void {
  ligado = novo;
  ouvintes.forEach((o) => o(novo));
  AsyncStorage.setItem(CHAVE_SOM, novo ? "1" : "0").catch(() => undefined);
}

/** Lê a preferência salva. Falha de leitura mantém o padrão (ligado) — nunca
 * trava nem propaga erro (lição do loading infinito achado em aparelho no B4). */
export async function carregarPreferenciaSom(): Promise<void> {
  try {
    const salvo = await AsyncStorage.getItem(CHAVE_SOM);
    if (salvo === "0" || salvo === "1") {
      ligado = salvo === "1";
      ouvintes.forEach((o) => o(ligado));
    }
  } catch {
    // Mantém o padrão.
  }
}

function garantirModoDeAudio(): void {
  if (modoConfigurado) return;
  modoConfigurado = true;
  try {
    void setAudioModeAsync({
      interruptionMode: "duckOthers",
      // Som de UI não deve continuar nem manter sessão viva em background:
      // o app fica horas aberto no painel e isso seguraria recurso de áudio
      // por toda a jornada.
      shouldPlayInBackground: false,
      playsInSilentMode: false,
      allowsRecording: false,
      shouldRouteThroughEarpiece: false,
    }).catch(() => undefined);
  } catch {
    // Módulo de áudio indisponível — `tocar` também vai falhar em silêncio.
  }
}

function obterPlayer(nome: NomeSom): AudioPlayer | null {
  if (players.has(nome)) return players.get(nome) ?? null;
  let player: AudioPlayer | null = null;
  try {
    player = createAudioPlayer(FONTES[nome] as never);
  } catch {
    player = null; // Memoiza a falha: não tenta recriar a cada toque.
  }
  players.set(nome, player);
  return player;
}

export function tocar(nome: NomeSom): void {
  if (!ligado) return;
  garantirModoDeAudio();
  const player = obterPlayer(nome);
  if (!player) return;
  try {
    // `seekTo` é assíncrono; tocar sem esperar dispararia do ponto anterior.
    void player
      .seekTo(0)
      .then(() => player.play())
      .catch(() => undefined);
  } catch {
    // Player inválido (aparelho sem áudio, sessão perdida) — segue em silêncio.
  }
}

/** Só para teste: descarta players e volta ao padrão. */
export function _resetarParaTeste(): void {
  players.clear();
  ligado = true;
  modoConfigurado = false;
  ouvintes.clear();
}
