import AsyncStorage from "@react-native-async-storage/async-storage";

import * as fila from "../queue";

function novoItem(overrides: Partial<Parameters<typeof fila.enfileirar>[0]> = {}) {
  return {
    eventId: overrides.eventId ?? `evt-${Math.random()}`,
    viagemId: "viagem-1",
    tripStudentId: "ts-1",
    acao: "cheguei" as const,
    deviceTimestamp: "2026-07-27T10:00:00.000Z",
    criadoEm: "2026-07-27T10:00:00.000Z",
    ...overrides,
  };
}

beforeEach(async () => {
  await AsyncStorage.clear();
});

describe("fila offline — persistência e ordem FIFO", () => {
  it("começa vazia", async () => {
    expect(await fila.listar()).toEqual([]);
    expect(await fila.tamanho()).toBe(0);
  });

  it("enfileira com seq crescente e mantém ordem FIFO", async () => {
    const a = await fila.enfileirar(novoItem({ eventId: "a" }));
    const b = await fila.enfileirar(novoItem({ eventId: "b" }));
    const c = await fila.enfileirar(novoItem({ eventId: "c" }));

    expect([a.seq, b.seq, c.seq]).toEqual([1, 2, 3]);

    const itens = await fila.listar();
    expect(itens.map((i) => i.eventId)).toEqual(["a", "b", "c"]);
  });

  it("item recém-enfileirado começa com tentativas=0 e ultimoErro=null", async () => {
    const item = await fila.enfileirar(novoItem());
    expect(item.tentativas).toBe(0);
    expect(item.ultimoErro).toBeNull();
  });

  it("sobrevive a uma releitura independente do storage (persistência real, não cache em memória)", async () => {
    await fila.enfileirar(novoItem({ eventId: "sobrevive" }));

    // queue.ts não guarda a fila em memória entre chamadas — cada
    // listar()/enfileirar()/remover() lê o AsyncStorage do zero. Isso É a
    // prova de durabilidade: não há estado de módulo que um restart do app
    // apagaria.
    const lidaDeNovo = await fila.listar();
    expect(lidaDeNovo).toHaveLength(1);
    expect(lidaDeNovo[0].eventId).toBe("sobrevive");
  });

  it("fila corrompida no storage vira fila vazia, não trava o app", async () => {
    await AsyncStorage.setItem("vaivem:fila:v1", "{ isso não é json válido");
    expect(await fila.listar()).toEqual([]);
  });
});

describe("fila offline — remover", () => {
  it("remove só o item alvo, preserva os demais em ordem", async () => {
    await fila.enfileirar(novoItem({ eventId: "a" }));
    await fila.enfileirar(novoItem({ eventId: "b" }));
    await fila.enfileirar(novoItem({ eventId: "c" }));

    await fila.remover("b");

    const itens = await fila.listar();
    expect(itens.map((i) => i.eventId)).toEqual(["a", "c"]);
  });

  it("remover um eventId inexistente é inofensivo", async () => {
    await fila.enfileirar(novoItem({ eventId: "a" }));
    await fila.remover("nao-existe");
    expect(await fila.tamanho()).toBe(1);
  });
});

describe("fila offline — registrarFalha", () => {
  it("incrementa tentativas e grava o erro só no item certo", async () => {
    await fila.enfileirar(novoItem({ eventId: "a" }));
    await fila.enfileirar(novoItem({ eventId: "b" }));

    await fila.registrarFalha("a", "falha de rede");
    await fila.registrarFalha("a", "falha de rede de novo");

    const itens = await fila.listar();
    const a = itens.find((i) => i.eventId === "a")!;
    const b = itens.find((i) => i.eventId === "b")!;

    expect(a.tentativas).toBe(2);
    expect(a.ultimoErro).toBe("falha de rede de novo");
    expect(b.tentativas).toBe(0);
    expect(b.ultimoErro).toBeNull();
  });
});

describe("fila offline — escritas concorrentes não se perdem", () => {
  it("N enfileiramentos disparados sem esperar um pelo outro preservam todos os itens", async () => {
    // Sem serialização (o `cadeia` de queue.ts), duas leituras-modificações-
    // escritas concorrentes do AsyncStorage perderiam uma das duas. Disparar
    // tudo de uma vez (sem await entre elas) é exatamente o cenário de dois
    // toques rápidos do motorista.
    const promessas = Array.from({ length: 10 }, (_, i) => fila.enfileirar(novoItem({ eventId: `item-${i}` })));
    await Promise.all(promessas);

    const itens = await fila.listar();
    expect(itens).toHaveLength(10);
    const seqs = itens.map((i) => i.seq).sort((a, b) => a - b);
    expect(seqs).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);
  });
});
