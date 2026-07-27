/**
 * Estado da viagem em andamento — otimista, reconciliado com o servidor.
 *
 * Fluxo de cada ação (Cheguei/Checkin/Checkout/Ausente/Desfazer...):
 * 1. Aplica a transição LOCALMENTE de imediato (otimista — CLAUDE.md §8,
 *    "a UI reflete o estado local otimista").
 * 2. Enfileira o evento (`shared/offline/sync.ts`) — mesmo online, sempre
 *    passa pela fila, o que unifica o caminho online/offline num só.
 * 3. Quando `sincronizado` chega, o `TripStudentOut` do servidor SUBSTITUI o
 *    estado local desse aluno (servidor é a autoridade final).
 * 4. Quando `conflito` chega (409/4xx definitivo), a tela inteira
 *    ressincroniza via GET — mais simples e mais seguro que tentar
 *    reconciliar um patch local depois de uma rejeição de domínio.
 *
 * §7.2 (CLAUDE.md) — resolução forçada de parada anterior pendente: checado
 * NO CLIENTE antes de abrir o diálogo do Cheguei, porque offline não há
 * servidor pra perguntar. A autoridade continua sendo o 409
 * `ParadaAnteriorPendenteError` — este guard é só UX (evita abrir o diálogo
 * pra depois falhar).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiError, NetworkError } from "../../shared/api/client";
import { endpoints } from "../../shared/api/endpoints";
import type { TripStudentOut, ViagemOut } from "../../shared/api/types";
import * as fila from "../../shared/offline/queue";
import { assinar, cancelarPendente, drenarFila, enfileirarEvento } from "../../shared/offline/sync";
import type { AcaoEvento } from "../../shared/offline/queue";

interface EstadoViagemStore {
  viagem: ViagemOut | null;
  tripStudents: TripStudentOut[];
  carregando: boolean;
  erro: string | null;
  pendentesPorTripStudent: Record<string, string[]>; // tripStudentId -> eventIds ainda na fila
  conflito: string | null; // mensagem do último 409/4xx, pra banner
}

function porOrdem(a: TripStudentOut, b: TripStudentOut): number {
  return a.ordem - b.ordem;
}

export function useViagemStore(viagemId: string) {
  const [estado, setEstado] = useState<EstadoViagemStore>({
    viagem: null,
    tripStudents: [],
    carregando: true,
    erro: null,
    pendentesPorTripStudent: {},
    conflito: null,
  });

  const montado = useRef(true);
  useEffect(
    () => () => {
      montado.current = false;
    },
    []
  );

  const aplicarSeMontado = useCallback((atualizador: (anterior: EstadoViagemStore) => EstadoViagemStore) => {
    if (montado.current) setEstado(atualizador);
  }, []);

  const recarregar = useCallback(async () => {
    aplicarSeMontado((anterior) => ({ ...anterior, carregando: true, erro: null }));
    try {
      const [viagem, tripStudents] = await Promise.all([
        endpoints.obterViagem(viagemId),
        endpoints.listarTripStudents(viagemId),
      ]);
      const itensFila = await fila.listar();
      const pendentesPorTripStudent: Record<string, string[]> = {};
      for (const item of itensFila) {
        if (item.viagemId !== viagemId) continue;
        (pendentesPorTripStudent[item.tripStudentId] ??= []).push(item.eventId);
      }
      aplicarSeMontado((anterior) => ({
        ...anterior,
        viagem,
        tripStudents: [...tripStudents].sort(porOrdem),
        pendentesPorTripStudent,
        carregando: false,
      }));
    } catch (erro) {
      const mensagem =
        erro instanceof ApiError
          ? erro.detail
          : erro instanceof NetworkError
            ? "Sem conexão — mostrando os últimos dados carregados."
            : "Não foi possível carregar a viagem.";
      aplicarSeMontado((anterior) => ({ ...anterior, carregando: false, erro: mensagem }));
    }
  }, [viagemId, aplicarSeMontado]);

  useEffect(() => {
    void recarregar();
  }, [recarregar]);

  // Reconciliação com o resultado da fila (sincronizado/conflito) — CLAUDE.md §8.
  useEffect(() => {
    const cancelar = assinar((evento) => {
      if (evento.tipo === "sincronizado" && evento.item.viagemId === viagemId) {
        aplicarSeMontado((anterior) => {
          const pendentes = { ...anterior.pendentesPorTripStudent };
          const restantes = (pendentes[evento.item.tripStudentId] ?? []).filter((id) => id !== evento.item.eventId);
          if (restantes.length > 0) pendentes[evento.item.tripStudentId] = restantes;
          else delete pendentes[evento.item.tripStudentId];

          const tripStudents = anterior.tripStudents
            .map((ts) => (ts.id === evento.resultado.id ? evento.resultado : ts))
            .sort(porOrdem);

          return { ...anterior, tripStudents, pendentesPorTripStudent: pendentes };
        });
      }

      if (evento.tipo === "conflito" && evento.item.viagemId === viagemId) {
        aplicarSeMontado((anterior) => {
          const pendentes = { ...anterior.pendentesPorTripStudent };
          const restantes = (pendentes[evento.item.tripStudentId] ?? []).filter((id) => id !== evento.item.eventId);
          if (restantes.length > 0) pendentes[evento.item.tripStudentId] = restantes;
          else delete pendentes[evento.item.tripStudentId];
          return { ...anterior, pendentesPorTripStudent: pendentes, conflito: evento.mensagem };
        });
        void recarregar(); // servidor é a autoridade — ressincroniza tudo
      }
    });
    return cancelar;
  }, [viagemId, aplicarSeMontado, recarregar]);

  const limparConflito = useCallback(() => {
    aplicarSeMontado((anterior) => ({ ...anterior, conflito: null }));
  }, [aplicarSeMontado]);

  /** §7.2 — alunos de ordem menor ainda em 'chegou' bloqueiam um novo Cheguei. */
  const paradasAnterioresPendentes = useCallback(
    (tripStudentId: string): TripStudentOut[] => {
      const alvo = estado.tripStudents.find((ts) => ts.id === tripStudentId);
      if (!alvo) return [];
      return estado.tripStudents.filter((ts) => ts.id !== alvo.id && ts.estado === "chegou" && ts.ordem < alvo.ordem);
    },
    [estado.tripStudents]
  );

  const aplicarLocal = useCallback(
    (tripStudentId: string, mudanca: Partial<TripStudentOut>, eventId: string) => {
      aplicarSeMontado((anterior) => ({
        ...anterior,
        tripStudents: anterior.tripStudents.map((ts) => (ts.id === tripStudentId ? { ...ts, ...mudanca } : ts)),
        pendentesPorTripStudent: {
          ...anterior.pendentesPorTripStudent,
          [tripStudentId]: [...(anterior.pendentesPorTripStudent[tripStudentId] ?? []), eventId],
        },
      }));
    },
    [aplicarSeMontado]
  );

  const executarAcao = useCallback(
    async (acao: AcaoEvento, tripStudentId: string, mudancaOtimista: Partial<TripStudentOut>) => {
      const item = await enfileirarEvento(acao, viagemId, tripStudentId);
      aplicarLocal(tripStudentId, mudancaOtimista, item.eventId);
      return item.eventId;
    },
    [viagemId, aplicarLocal]
  );

  const marcarCheguei = useCallback(
    (tripStudentId: string) => executarAcao("cheguei", tripStudentId, { estado: "chegou" }),
    [executarAcao]
  );

  const marcarCheckin = useCallback(
    (tripStudentId: string) => executarAcao("checkin", tripStudentId, { estado: "a_bordo" }),
    [executarAcao]
  );

  const marcarCheckout = useCallback(
    (tripStudentId: string) => executarAcao("checkout", tripStudentId, { estado: "entregue" }),
    [executarAcao]
  );

  const marcarAusente = useCallback(
    (tripStudentId: string) => executarAcao("ausente", tripStudentId, { estado: "ausente" }),
    [executarAcao]
  );

  const desfazerChegada = useCallback(
    (tripStudentId: string) => executarAcao("desfazer_chegada", tripStudentId, { estado: "aguardando" }),
    [executarAcao]
  );

  /** Undo de 30s do Checkin (CLAUDE.md §8). Se o Checkin ainda está na fila
   * (não sincronizou), cancela localmente — não gasta a janela de 60s do
   * servidor. Se já foi enviado, enfileira um `desfazer_checkin` de verdade. */
  const desfazerCheckin = useCallback(
    async (tripStudentId: string, eventIdDoCheckin: string | null) => {
      const aindaNaFila = eventIdDoCheckin
        ? (await fila.listar()).some((i) => i.eventId === eventIdDoCheckin)
        : false;

      if (aindaNaFila && eventIdDoCheckin) {
        await cancelarPendente(eventIdDoCheckin);
        aplicarSeMontado((anterior) => {
          const pendentes = { ...anterior.pendentesPorTripStudent };
          pendentes[tripStudentId] = (pendentes[tripStudentId] ?? []).filter((id) => id !== eventIdDoCheckin);
          if (pendentes[tripStudentId]?.length === 0) delete pendentes[tripStudentId];
          return {
            ...anterior,
            tripStudents: anterior.tripStudents.map((ts) =>
              ts.id === tripStudentId ? { ...ts, estado: "chegou" as const } : ts
            ),
            pendentesPorTripStudent: pendentes,
          };
        });
        return;
      }

      await executarAcao("desfazer_checkin", tripStudentId, { estado: "chegou" });
    },
    [executarAcao, aplicarSeMontado]
  );

  /** Reordenar é online-only (ver docstring de `shared/offline/queue.ts`) —
   * só válido antes do Cheguei, tipicamente perto da garagem. */
  const reordenar = useCallback(
    async (itens: { trip_student_id: string; ordem: number }[]) => {
      const atualizados = await endpoints.reordenarTripStudents(viagemId, { itens });
      aplicarSeMontado((anterior) => {
        const porId = new Map(atualizados.map((ts) => [ts.id, ts]));
        return {
          ...anterior,
          tripStudents: anterior.tripStudents.map((ts) => porId.get(ts.id) ?? ts).sort(porOrdem),
        };
      });
    },
    [viagemId, aplicarSeMontado]
  );

  const todosNaoTerminais = useMemo(
    () => estado.tripStudents.filter((ts) => ts.estado !== "entregue" && ts.estado !== "ausente"),
    [estado.tripStudents]
  );

  return {
    ...estado,
    recarregar,
    limparConflito,
    paradasAnterioresPendentes,
    marcarCheguei,
    marcarCheckin,
    marcarCheckout,
    marcarAusente,
    desfazerChegada,
    desfazerCheckin,
    reordenar,
    todosNaoTerminais,
    drenarFilaAgora: drenarFila,
  };
}

export type ViagemStore = ReturnType<typeof useViagemStore>;
