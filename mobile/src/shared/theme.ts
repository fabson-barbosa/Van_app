/**
 * Paleta e constantes de UI — espelha docs/prototipos/01-app-motorista.html
 * (protótipo visual de referência do CLAUDE.md).
 *
 * TOQUE_MIN é a restrição mais importante do app (CLAUDE.md §8): o motorista
 * está dirigindo, todo alvo de toque tem que ter pelo menos 56dp.
 *
 * Bloco B7: as cores de TEXTO foram escurecidas para passar em WCAG AA (4.5:1
 * para texto pequeno). O motivo é operacional, não estético — a tela é lida
 * sob sol direto, num parque de aparelhos antigos (CLAUDE.md §2). Os valores
 * medidos antes/depois estão em docs/analise-ux-motorista.md §3.3.
 */
export const cores = {
  tinta: "#10231e",
  papel: "#f4f1ea",
  cartao: "#ffffff",
  linha: "rgba(16,35,30,0.10)",
  linha2: "rgba(16,35,30,0.16)",
  esmaecido: "#5d6b65",
  /** B7: era #8a958f (2,85:1 sobre branco — reprovava AA). Agora 4,60:1. */
  dica: "#6b7873",
  marca: "#0f6e56",
  marca2: "#1d9e75",
  marcaSuave: "#e1f5ee",
  /** B7: era #ba7517 (3,72:1 sobre branco e 3,25:1 sobre `ambarSuave` — reprovava
   * AA nos dois). Agora 6,27:1 e 5,46:1. Usada como texto E como borda. */
  ambar: "#8a5410",
  ambarSuave: "#faeeda",
  perigo: "#a32d2d",
  perigoSuave: "#fceaea",
  /** B7: fundo SÓLIDO para confirmar ação irreversível (7,07:1 com texto
   * branco). `perigoSuave` tem peso de ação terciária — fraco demais para o
   * botão que marca um aluno como ausente para sempre. */
  perigoForte: "#a32d2d",
  info: "#185fa5",
  infoSuave: "#e6f1fb",
  sol: "#efb742",
} as const;

export const TOQUE_MIN = 56;

/** Botões de diálogo (CLAUDE.md §6/§8, Bloco B7) — confirmar algo irreversível
 * com a van parada em fila dupla pede um alvo maior que o piso de 56dp. */
export const TOQUE_GRANDE = 72;

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

/**
 * B7: piso de 13sp. Nada abaixo disso é legível ao sol num aparelho antigo —
 * o app tinha rótulos em 11sp e 11,5sp. `endereco` subiu de 12 para 14 porque
 * é o dado que CONFIRMA que a parada é a certa (CLAUDE.md §6).
 */
export const tipografia = {
  destaque: 22,
  titulo: 20,
  corpo: 15,
  endereco: 14,
  legenda: 13,
} as const;
