import AsyncStorage from "@react-native-async-storage/async-storage";

jest.mock("../uuid", () => ({ gerarUuid: jest.fn() }));
jest.mock("../../api/endpoints", () => ({ chamarAcaoEvento: jest.fn() }));
jest.mock("@react-native-community/netinfo", () => ({
  __esModule: true,
  default: { addEventListener: jest.fn(() => () => undefined) },
}));

import { chamarAcaoEvento } from "../../api/endpoints";
import { ApiError, NetworkError } from "../../api/client";
import * as fila from "../queue";
import type { ItemFila } from "../queue";
import { gerarUuid } from "../uuid";
import {
  _resetParaTestes,
  assinar,
  drenarFila,
  enfileirarEvento,
  estaPausadoPorAuth,
  retomarAposRelogin,
  type EventoSync,
} from "../sync";

const chamarAcaoEventoMock = chamarAcaoEvento as jest.Mock;
const gerarUuidMock = gerarUuid as jest.Mock;

function itemBase(overrides: Partial<Omit<ItemFila, "seq" | "tentativas" | "ultimoErro">> = {}) {
  return {
    eventId: overrides.eventId ?? `evt-${Math.random()}`,
    viagemId: "v-1",
    tripStudentId: "ts-1",
    acao: "cheguei" as const,
    deviceTimestamp: "2026-07-27T10:00:00.000Z",
    criadoEm: "2026-07-27T10:00:00.000Z",
    ...overrides,
  };
}

function tripStudentFake(overrides: Record<string, unknown> = {}) {
  return {
    id: "ts-1",
    viagem_id: "v-1",
    aluno_id: "a-1",
    parada_id: null,
    ordem: 1,
    estado: "chegou",
    chegou_em: null,
    checkin_em: null,
    checkout_em: null,
    ausente_em: null,
    aluno_nome: "Fulano",
    parada_endereco: null,
    ...overrides,
  };
}

async function coletarEventos(): Promise<{ eventos: EventoSync[]; cancelar: () => void }> {
  const eventos: EventoSync[] = [];
  const cancelar = assinar((e) => eventos.push(e));
  return { eventos, cancelar };
}

/** Espera (com timers REAIS) até uma condição ficar verdadeira — usado pra
 * observar o resultado de chamadas fire-and-forget (`enfileirarEvento`,
 * `retomarAposRelogin`) sem depender de contar microtasks manualmente. */
async function esperarAte(condicao: () => boolean | Promise<boolean>, tentativas = 50): Promise<void> {
  for (let i = 0; i < tentativas; i++) {
    if (await condicao()) return;
    await new Promise((resolve) => setTimeout(resolve, 5));
  }
  throw new Error("esperarAte: condição não ficou verdadeira a tempo");
}

beforeEach(async () => {
  await AsyncStorage.clear();
  chamarAcaoEventoMock.mockReset();
  gerarUuidMock.mockReset();
  let contador = 0;
  gerarUuidMock.mockImplementation(() => `uuid-${++contador}`);
  _resetParaTestes();
});

describe("drenarFila — sucesso", () => {
  it("2xx remove da fila e emite 'sincronizado' com o TripStudentOut do servidor", async () => {
    await fila.enfileirar(itemBase({ eventId: "a" }));
    chamarAcaoEventoMock.mockResolvedValueOnce(tripStudentFake({ estado: "chegou" }));

    const { eventos, cancelar } = await coletarEventos();
    await drenarFila();
    cancelar();

    expect(await fila.tamanho()).toBe(0);
    expect(chamarAcaoEventoMock).toHaveBeenCalledTimes(1);
    expect(eventos.filter((e) => e.tipo === "sincronizado")).toHaveLength(1);
  });

  it("processa a fila em ordem estritamente sequencial (FIFO), um por vez", async () => {
    await fila.enfileirar(itemBase({ eventId: "a", tripStudentId: "ts-a" }));
    await fila.enfileirar(itemBase({ eventId: "b", tripStudentId: "ts-b" }));
    await fila.enfileirar(itemBase({ eventId: "c", tripStudentId: "ts-c" }));

    const ordem: string[] = [];
    chamarAcaoEventoMock.mockImplementation(async (_acao, _viagemId, tripStudentId) => {
      ordem.push(tripStudentId);
      return tripStudentFake({ id: tripStudentId });
    });

    await drenarFila();

    expect(ordem).toEqual(["ts-a", "ts-b", "ts-c"]);
    expect(await fila.tamanho()).toBe(0);
  });
});

describe("drenarFila — 401 pausa tudo, fila preservada", () => {
  it("não tenta o próximo item depois de um 401, e mantém ambos na fila", async () => {
    await fila.enfileirar(itemBase({ eventId: "a" }));
    await fila.enfileirar(itemBase({ eventId: "b" }));
    chamarAcaoEventoMock.mockRejectedValueOnce(new ApiError(401, "Sessão expirada."));

    const { eventos, cancelar } = await coletarEventos();
    await drenarFila();
    cancelar();

    expect(chamarAcaoEventoMock).toHaveBeenCalledTimes(1); // não tentou o "b"
    expect(await fila.tamanho()).toBe(2); // nada removido — fila preservada
    expect(estaPausadoPorAuth()).toBe(true);
    expect(eventos.some((e) => e.tipo === "nao_autorizado")).toBe(true);
  });

  it("retomarAposRelogin() destrava e a drenagem continua de onde parou", async () => {
    await fila.enfileirar(itemBase({ eventId: "a" }));
    chamarAcaoEventoMock.mockRejectedValueOnce(new ApiError(401, "Sessão expirada."));
    await drenarFila();
    expect(estaPausadoPorAuth()).toBe(true);

    chamarAcaoEventoMock.mockResolvedValueOnce(tripStudentFake());
    retomarAposRelogin();
    // retomarAposRelogin dispara drenarFila() sem esperar (fire-and-forget) —
    // espera com timers reais até a fila esvaziar em vez de contar microtasks.
    await esperarAte(async () => (await fila.tamanho()) === 0);

    expect(estaPausadoPorAuth()).toBe(false);
  });
});

describe("drenarFila — 4xx/409 é definitivo (bandeja de conflitos), continua a fila", () => {
  it("remove o item, emite 'conflito' e segue pro próximo", async () => {
    await fila.enfileirar(itemBase({ eventId: "a", tripStudentId: "ts-a" }));
    await fila.enfileirar(itemBase({ eventId: "b", tripStudentId: "ts-b" }));

    chamarAcaoEventoMock
      .mockRejectedValueOnce(new ApiError(409, "Transição inválida."))
      .mockResolvedValueOnce(tripStudentFake({ id: "ts-b" }));

    const { eventos, cancelar } = await coletarEventos();
    await drenarFila();
    cancelar();

    expect(chamarAcaoEventoMock).toHaveBeenCalledTimes(2); // não parou no 409
    expect(await fila.tamanho()).toBe(0);
    const conflitos = eventos.filter((e) => e.tipo === "conflito");
    expect(conflitos).toHaveLength(1);
    expect((conflitos[0] as { mensagem: string }).mensagem).toBe("Transição inválida.");
  });
});

describe("drenarFila — rede/5xx é transitório, PARA a drenagem (não pula, não remove)", () => {
  it("NetworkError não remove o item e não tenta o próximo", async () => {
    await fila.enfileirar(itemBase({ eventId: "a" }));
    await fila.enfileirar(itemBase({ eventId: "b" }));
    chamarAcaoEventoMock.mockRejectedValueOnce(new NetworkError());

    await drenarFila();

    expect(chamarAcaoEventoMock).toHaveBeenCalledTimes(1);
    expect(await fila.tamanho()).toBe(2);
    const itens = await fila.listar();
    expect(itens[0].tentativas).toBe(1);
    expect(itens[0].ultimoErro).toBeTruthy();
  });

  it("5xx tem o mesmo tratamento de transitório que NetworkError", async () => {
    await fila.enfileirar(itemBase({ eventId: "a" }));
    chamarAcaoEventoMock.mockRejectedValueOnce(new ApiError(500, "Erro interno"));

    await drenarFila();

    expect(await fila.tamanho()).toBe(1);
    const itens = await fila.listar();
    expect(itens[0].tentativas).toBe(1);
  });

  it("uma chamada concorrente a drenarFila() enquanto já está drenando é um no-op", async () => {
    await fila.enfileirar(itemBase({ eventId: "a" }));
    let resolverPrimeira: (valor: unknown) => void = () => undefined;
    chamarAcaoEventoMock.mockImplementationOnce(
      () => new Promise((resolve) => { resolverPrimeira = resolve; })
    );

    const primeiraChamada = drenarFila();
    const segundaChamada = drenarFila(); // deve retornar imediatamente, sem reentrar

    // Só resolve depois que a 1ª chamada realmente alcançou chamarAcaoEvento
    // (passou pelo await fila.listar()) — resolver cedo demais resolveria a
    // promise ERRADA (o placeholder de antes do mock rodar) e travaria o teste.
    await esperarAte(() => chamarAcaoEventoMock.mock.calls.length > 0);
    resolverPrimeira(tripStudentFake());
    await Promise.all([primeiraChamada, segundaChamada]);

    expect(chamarAcaoEventoMock).toHaveBeenCalledTimes(1);
  });
});

describe("enfileirarEvento", () => {
  it("gera o event_id UMA vez, persiste o item e devolve o eventId gerado", async () => {
    // Evita que o drenarFila disparado internamente termine durante o teste
    // (senão a asserção de tamanho da fila viraria uma corrida).
    chamarAcaoEventoMock.mockImplementation(() => new Promise(() => undefined));

    const item = await enfileirarEvento("checkin", "v-1", "ts-9");

    expect(item.eventId).toBe("uuid-1");
    expect(gerarUuidMock).toHaveBeenCalledTimes(1);

    const itens = await fila.listar();
    expect(itens).toHaveLength(1);
    expect(itens[0]).toMatchObject({ acao: "checkin", viagemId: "v-1", tripStudentId: "ts-9", eventId: "uuid-1" });
  });
});
