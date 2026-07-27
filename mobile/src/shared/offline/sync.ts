/**
 * Worker de drenagem da fila offline — CLAUDE.md §8.
 *
 * Estritamente sequencial (um item por vez, FIFO): o backend valida
 * transições (§7.2 — parada anterior pendente; janela do desfazer-checkin),
 * então paralelizar quebraria a ordem que a máquina de estados exige.
 *
 * Tratamento por tipo de falha:
 * - 2xx: remove da fila, emite `sincronizado` (quem ouve aplica o
 *   `TripStudentOut` retornado sobre o estado local — servidor é autoridade).
 * - 401: PARA tudo, emite `nao_autorizado` (fila preservada) — só
 *   `retomarAposRelogin()` destrava.
 * - 4xx (inclui 409 de domínio): definitivo — reenviar não muda o resultado.
 *   Remove da fila, emite `conflito` pra UI mostrar a bandeja.
 * - NetworkError / 5xx: transitório — NÃO remove, NÃO pula. Para a drenagem
 *   inteira (ordem importa) e agenda nova tentativa com backoff.
 */
import { AppState, AppStateStatus } from "react-native";
import NetInfo from "@react-native-community/netinfo";

import { ApiError, NetworkError } from "../api/client";
import { chamarAcaoEvento } from "../api/endpoints";
import type { EventoAlunoRequest, TripStudentOut } from "../api/types";
import * as fila from "./queue";
import type { AcaoEvento, ItemFila } from "./queue";
import { agoraISO } from "./relogio";
import { gerarUuid } from "./uuid";

export type EventoSync =
  | { tipo: "sincronizado"; item: ItemFila; resultado: TripStudentOut }
  | { tipo: "conflito"; item: ItemFila; mensagem: string }
  | { tipo: "nao_autorizado" }
  | { tipo: "fila_mudou"; quantidade: number };

type Ouvinte = (evento: EventoSync) => void;

const ouvintes = new Set<Ouvinte>();

export function assinar(ouvinte: Ouvinte): () => void {
  ouvintes.add(ouvinte);
  return () => {
    ouvintes.delete(ouvinte);
  };
}

function emitir(evento: EventoSync): void {
  ouvintes.forEach((ouvinte) => ouvinte(evento));
}

const BACKOFF_MIN_MS = 2_000;
const BACKOFF_MAX_MS = 60_000;

let drenando = false;
let pausadoPorAuth = false;
let timerBackoff: ReturnType<typeof setTimeout> | null = null;
let tentativaBackoffAtual = 0;

async function emitirTamanho(): Promise<void> {
  emitir({ tipo: "fila_mudou", quantidade: await fila.tamanho() });
}

/** Enfileira o evento e dispara uma tentativa de drenagem imediata (não
 * espera por ela — a UI já aplicou o estado otimista antes de chamar isto). */
export async function enfileirarEvento(
  acao: AcaoEvento,
  viagemId: string,
  tripStudentId: string
): Promise<ItemFila> {
  const agora = agoraISO();
  const item = await fila.enfileirar({
    eventId: gerarUuid(),
    viagemId,
    tripStudentId,
    acao,
    deviceTimestamp: agora,
    criadoEm: agora,
  });
  await emitirTamanho();
  void drenarFila();
  return item;
}

/** Remove um item ainda não sincronizado — usado pelo undo de 30s do Checkin
 * quando o evento nem chegou a sair do aparelho (BarraUndo.tsx). */
export async function cancelarPendente(eventId: string): Promise<void> {
  await fila.remover(eventId);
  await emitirTamanho();
}

function agendarNovaTentativa(): void {
  if (timerBackoff) return;
  const espera = Math.min(BACKOFF_MIN_MS * 2 ** tentativaBackoffAtual, BACKOFF_MAX_MS);
  tentativaBackoffAtual += 1;
  timerBackoff = setTimeout(() => {
    timerBackoff = null;
    void drenarFila();
  }, espera);
}

export async function drenarFila(): Promise<void> {
  if (drenando || pausadoPorAuth) return;
  drenando = true;
  try {
    for (;;) {
      const itens = await fila.listar();
      if (itens.length === 0) return;
      const item = itens[0];

      try {
        const payload: EventoAlunoRequest = {
          event_id: item.eventId,
          device_timestamp: item.deviceTimestamp,
          device_enviado_em: agoraISO(),
        };
        const resultado = await chamarAcaoEvento(item.acao, item.viagemId, item.tripStudentId, payload);

        await fila.remover(item.eventId);
        await emitirTamanho();
        emitir({ tipo: "sincronizado", item, resultado });
        tentativaBackoffAtual = 0;
      } catch (erro) {
        if (erro instanceof ApiError && erro.status === 401) {
          pausadoPorAuth = true;
          emitir({ tipo: "nao_autorizado" });
          return;
        }

        if (erro instanceof ApiError && erro.status < 500) {
          // 4xx (inclui 409 de domínio) — definitivo, reenviar não ajuda.
          await fila.remover(item.eventId);
          await emitirTamanho();
          emitir({ tipo: "conflito", item, mensagem: erro.detail });
          continue;
        }

        // NetworkError ou 5xx — transitório. Não remove, não pula: para aqui.
        const mensagem = erro instanceof Error ? erro.message : String(erro);
        await fila.registrarFalha(item.eventId, mensagem);
        agendarNovaTentativa();
        return;
      }
    }
  } finally {
    drenando = false;
  }
}

/** Chamado depois de um relogin bem-sucedido — destrava a drenagem pausada por 401. */
export function retomarAposRelogin(): void {
  pausadoPorAuth = false;
  tentativaBackoffAtual = 0;
  void drenarFila();
}

export function estaPausadoPorAuth(): boolean {
  return pausadoPorAuth;
}

/** Liga os gatilhos automáticos (reconexão, app voltando ao primeiro plano).
 * Retorna a função de limpeza — chamar no unmount da tela/raiz do app. */
export function iniciarDrenagemAutomatica(): () => void {
  void drenarFila();

  const cancelarNetInfo = NetInfo.addEventListener((estado) => {
    if (estado.isConnected) void drenarFila();
  });

  const aoMudarAppState = (proximoEstado: AppStateStatus): void => {
    if (proximoEstado === "active") void drenarFila();
  };
  const assinaturaAppState = AppState.addEventListener("change", aoMudarAppState);

  return () => {
    cancelarNetInfo();
    assinaturaAppState.remove();
    if (timerBackoff) {
      clearTimeout(timerBackoff);
      timerBackoff = null;
    }
  };
}

/** Só para testes — reseta o estado interno do módulo entre casos. */
export function _resetParaTestes(): void {
  drenando = false;
  pausadoPorAuth = false;
  tentativaBackoffAtual = 0;
  if (timerBackoff) {
    clearTimeout(timerBackoff);
    timerBackoff = null;
  }
  ouvintes.clear();
}

export { NetworkError };
