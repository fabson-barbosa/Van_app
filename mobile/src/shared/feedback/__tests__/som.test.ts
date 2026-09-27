/**
 * Preferência e disparo dos sons de confirmação (Bloco B8).
 *
 * O que importa travar aqui não é o áudio (nada toca em teste), é o CONTRATO:
 *
 * - o módulo **nunca lança** — é reforço, não canal primário, igual ao háptico;
 * - `somLigado()` é **síncrono**, porque os pontos de chamada são handlers de
 *   toque e um `await` atrasaria o som do próprio toque;
 * - `seekTo(0)` acontece **antes** de `play()`, senão o segundo toque no mesmo
 *   som não emite nada (o player está parado no fim da amostra);
 * - `feedbackSincronizado` **não toca som** — a fila drena quando o sinal volta,
 *   possivelmente minutos depois do toque, sem contexto para o motorista.
 */
import AsyncStorage from "@react-native-async-storage/async-storage";

import {
  feedbackAceito,
  feedbackConcluido,
  feedbackDesfeito,
  feedbackErro,
  feedbackSincronizado,
} from "../index";
import { carregarPreferenciaSom, definirSom, somLigado, tocar, _resetarParaTeste } from "../som";

// Os nomes têm que começar com `mock`: `jest.mock` é hoisted acima das
// declarações, e o Babel só libera o acesso a variáveis externas dentro da
// factory quando o nome tem esse prefixo.
const mockPlay = jest.fn();
const mockSeekTo = jest.fn((_segundos: number) => Promise.resolve());
const mockSetAudioMode = jest.fn((_modo: Record<string, unknown>) => Promise.resolve());
const mockCreatePlayer = jest.fn((_fonte: unknown) => ({ play: mockPlay, seekTo: mockSeekTo }));

jest.mock("expo-audio", () => ({
  createAudioPlayer: (fonte: unknown) => mockCreatePlayer(fonte),
  setAudioModeAsync: (modo: Record<string, unknown>) => mockSetAudioMode(modo),
}));

jest.mock("expo-haptics", () => ({
  impactAsync: jest.fn(() => Promise.resolve()),
  notificationAsync: jest.fn(() => Promise.resolve()),
  ImpactFeedbackStyle: { Medium: "Medium" },
  NotificationFeedbackType: { Success: "Success", Error: "Error" },
}));

beforeEach(async () => {
  _resetarParaTeste();
  jest.clearAllMocks();
  await AsyncStorage.clear();
});

describe("preferência", () => {
  it("vem ligada por padrão", () => {
    expect(somLigado()).toBe(true);
  });

  it("desligar impede qualquer chamada ao áudio", () => {
    definirSom(false);
    tocar("aceito");
    expect(mockCreatePlayer).not.toHaveBeenCalled();
    expect(mockPlay).not.toHaveBeenCalled();
  });

  it("é persistida e relida", async () => {
    definirSom(false);
    _resetarParaTeste(); // simula reabrir o app
    expect(somLigado()).toBe(true);

    await carregarPreferenciaSom();
    expect(somLigado()).toBe(false);
  });

  it("leitura que falha mantém o padrão em vez de propagar erro", async () => {
    const espia = jest.spyOn(AsyncStorage, "getItem").mockRejectedValueOnce(new Error("storage cheio"));

    await expect(carregarPreferenciaSom()).resolves.toBeUndefined();
    expect(somLigado()).toBe(true);

    espia.mockRestore();
  });
});

describe("tocar", () => {
  it("configura o modo de áudio como duckOthers na primeira vez", () => {
    tocar("aceito");
    expect(mockSetAudioMode).toHaveBeenCalledTimes(1);
    expect(mockSetAudioMode.mock.calls[0][0]).toMatchObject({ interruptionMode: "duckOthers" });
  });

  it("não reconfigura o modo de áudio a cada som", () => {
    tocar("aceito");
    tocar("erro");
    tocar("concluido");
    expect(mockSetAudioMode).toHaveBeenCalledTimes(1);
  });

  it("volta ao início antes de tocar, para o mesmo som poder repetir", async () => {
    tocar("aceito");
    await Promise.resolve();
    await Promise.resolve();

    expect(mockSeekTo).toHaveBeenCalledWith(0);
    expect(mockPlay).toHaveBeenCalledTimes(1);
  });

  it("reaproveita o player do mesmo som e cria um por nome", () => {
    tocar("aceito");
    tocar("aceito");
    expect(mockCreatePlayer).toHaveBeenCalledTimes(1);

    tocar("erro");
    expect(mockCreatePlayer).toHaveBeenCalledTimes(2);
  });

  // Contrato "nunca lança": em aparelho sem áudio ou com o módulo nativo ausente
  // (Expo Go em certos aparelhos), `createAudioPlayer` estoura. Se isso vazar,
  // derruba o handler do Cheguei por causa de um efeito sonoro.
  it("não lança quando a criação do player falha, e não tenta de novo", () => {
    mockCreatePlayer.mockImplementationOnce(() => {
      throw new Error("sem módulo de áudio");
    });

    expect(() => tocar("aceito")).not.toThrow();
    expect(() => tocar("aceito")).not.toThrow();
    // A falha é memoizada: uma tentativa só, não uma por toque.
    expect(mockCreatePlayer).toHaveBeenCalledTimes(1);
    expect(mockPlay).not.toHaveBeenCalled();
  });

  it("não lança quando a reprodução falha", async () => {
    mockSeekTo.mockRejectedValueOnce(new Error("sessão de áudio perdida"));
    expect(() => tocar("aceito")).not.toThrow();
    await Promise.resolve();
    expect(mockPlay).not.toHaveBeenCalled();
  });
});

describe("semântica do feedback", () => {
  it("cada evento de domínio usa uma amostra distinta", () => {
    feedbackAceito();
    feedbackConcluido();
    feedbackDesfeito();
    feedbackErro();

    // Quatro players distintos = quatro sons distintos. Se dois eventos
    // compartilhassem amostra, o motorista não distinguiria pelo ouvido.
    expect(mockCreatePlayer).toHaveBeenCalledTimes(4);
  });

  it("sincronização da fila não toca som — só vibra", () => {
    feedbackSincronizado();

    expect(mockCreatePlayer).not.toHaveBeenCalled();
    expect(mockPlay).not.toHaveBeenCalled();
  });
});
