/**
 * Paleta e constantes de UI — espelha docs/prototipos/01-app-motorista.html
 * (protótipo visual de referência do CLAUDE.md).
 *
 * TOQUE_MIN é a restrição mais importante do app (CLAUDE.md §8): o motorista
 * está dirigindo, todo alvo de toque tem que ter pelo menos 56dp.
 */
export const cores = {
  tinta: "#10231e",
  papel: "#f4f1ea",
  cartao: "#ffffff",
  linha: "rgba(16,35,30,0.10)",
  linha2: "rgba(16,35,30,0.16)",
  esmaecido: "#5d6b65",
  dica: "#8a958f",
  marca: "#0f6e56",
  marca2: "#1d9e75",
  marcaSuave: "#e1f5ee",
  ambar: "#ba7517",
  ambarSuave: "#faeeda",
  perigo: "#a32d2d",
  perigoSuave: "#fceaea",
  info: "#185fa5",
  infoSuave: "#e6f1fb",
  sol: "#efb742",
} as const;

export const TOQUE_MIN = 56;

export const espacamento = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
} as const;

export const raio = {
  sm: 10,
  md: 14,
  lg: 18,
} as const;

export const tipografia = {
  titulo: 20,
  corpo: 15,
  legenda: 13,
} as const;
