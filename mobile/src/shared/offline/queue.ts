/**
 * Fila offline persistente — CLAUDE.md §8 ("van sem sinal é o caso normal").
 *
 * Cobre só os 6 eventos por aluno (Cheguei/Checkin/Checkout/Ausente/
 * Desfazer chegada/Desfazer checkin): é aí que a viagem passa horas sem
 * sinal. Iniciar/finalizar viagem, reordenar e "estou atrasado" são ações
 * de fronteira (início/fim do turno, ou raras) tratadas como online-only na
 * UI (erro claro + tentar de novo) — não entram nesta fila. Ver
 * PROGRESSO.md (Bloco B4) para o racional completo dessa fronteira de
 * escopo.
 *
 * `eventId` é gerado UMA VEZ, no momento do toque (`sync.ts::enfileirarEvento`),
 * e nunca muda entre tentativas — é a chave de idempotência que o backend
 * (`event_id`, migration 0008) usa para nunca duplicar um evento reenviado.
 *
 * Persistência via AsyncStorage (um blob JSON só, chave `vaivem:fila:v1`).
 * Todo acesso passa por `serializado()` — sem isso, dois toques rápidos (ou
 * o app enfileirando enquanto a drenagem em background está no meio de um
 * `remover`) poderiam ler-modificar-escrever em cima um do outro e perder um
 * item; AsyncStorage não tem transação.
 */
import AsyncStorage from "@react-native-async-storage/async-storage";

export type AcaoEvento =
  | "cheguei"
  | "checkin"
  | "checkout"
  | "ausente"
  | "desfazer_chegada"
  | "desfazer_checkin";

export interface ItemFila {
  eventId: string;
  seq: number;
  viagemId: string;
  tripStudentId: string;
  acao: AcaoEvento;
  /** Instante do TOQUE (device), carimbado uma vez, nunca recarimbado em reenvios. */
  deviceTimestamp: string;
  criadoEm: string;
  tentativas: number;
  ultimoErro: string | null;
}

const CHAVE = "vaivem:fila:v1";

let cadeia: Promise<unknown> = Promise.resolve();

function serializado<T>(tarefa: () => Promise<T>): Promise<T> {
  const resultado = cadeia.then(tarefa, tarefa);
  cadeia = resultado.then(
    () => undefined,
    () => undefined
  );
  return resultado;
}

async function lerBruto(): Promise<ItemFila[]> {
  const json = await AsyncStorage.getItem(CHAVE);
  if (!json) return [];
  try {
    const itens = JSON.parse(json);
    return Array.isArray(itens) ? (itens as ItemFila[]) : [];
  } catch {
    return []; // fila corrompida — melhor perder a fila que travar o app na inicialização
  }
}

async function escreverBruto(itens: ItemFila[]): Promise<void> {
  await AsyncStorage.setItem(CHAVE, JSON.stringify(itens));
}

/** Itens em ordem FIFO (por `seq`, não pela ordem em que o storage devolve). */
export function listar(): Promise<ItemFila[]> {
  return serializado(async () => {
    const itens = await lerBruto();
    return [...itens].sort((a, b) => a.seq - b.seq);
  });
}

export function tamanho(): Promise<number> {
  return listar().then((itens) => itens.length);
}

export function enfileirar(novo: Omit<ItemFila, "seq" | "tentativas" | "ultimoErro">): Promise<ItemFila> {
  return serializado(async () => {
    const itens = await lerBruto();
    const proximoSeq = itens.reduce((max, i) => Math.max(max, i.seq), 0) + 1;
    const item: ItemFila = { ...novo, seq: proximoSeq, tentativas: 0, ultimoErro: null };
    await escreverBruto([...itens, item]);
    return item;
  });
}

export function remover(eventId: string): Promise<void> {
  return serializado(async () => {
    const itens = await lerBruto();
    await escreverBruto(itens.filter((i) => i.eventId !== eventId));
  });
}

export function registrarFalha(eventId: string, erro: string): Promise<void> {
  return serializado(async () => {
    const itens = await lerBruto();
    const atualizados = itens.map((i) =>
      i.eventId === eventId ? { ...i, tentativas: i.tentativas + 1, ultimoErro: erro } : i
    );
    await escreverBruto(atualizados);
  });
}

/** Só para testes/depuração — nunca chamado pelo fluxo normal do app. */
export function limparTudo(): Promise<void> {
  return serializado(async () => {
    await escreverBruto([]);
  });
}
