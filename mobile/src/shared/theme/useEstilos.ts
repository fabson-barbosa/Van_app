/**
 * `useEstilos` — folha de estilo dependente de paleta (Bloco B8).
 *
 * `StyleSheet.create` é estático: com duas paletas, cada componente precisa de
 * uma folha por paleta. Recriar a folha em todo render funcionaria, mas
 * descartaria a otimização do `StyleSheet` (registro nativo reaproveitado) numa
 * `FlatList` de doze alunos que já roda em aparelho antigo.
 *
 * Então a fábrica é memoizada por (fábrica, paleta) num `WeakMap`: cada
 * componente produz no máximo duas folhas na vida do processo, e trocar de tema
 * na terceira vez não recalcula nada. A chave é a identidade da função — por
 * isso a fábrica tem que ser declarada no módulo, nunca inline no componente.
 */
import { useMemo } from "react";

import type { Paleta } from "./paleta";

type Fabrica<T> = (cores: Paleta) => T;

const cache = new WeakMap<Fabrica<unknown>, Map<string, unknown>>();

export function estilosPara<T>(fabrica: Fabrica<T>, cores: Paleta): T {
  let porPaleta = cache.get(fabrica as Fabrica<unknown>);
  if (!porPaleta) {
    porPaleta = new Map();
    cache.set(fabrica as Fabrica<unknown>, porPaleta);
  }
  const existente = porPaleta.get(cores.nome);
  if (existente) return existente as T;

  const folha = fabrica(cores);
  porPaleta.set(cores.nome, folha);
  return folha;
}

/** Açúcar para usar dentro de componente, já com a paleta em vigor. */
export function useEstilos<T>(fabrica: Fabrica<T>, cores: Paleta): T {
  return useMemo(() => estilosPara(fabrica, cores), [fabrica, cores]);
}
