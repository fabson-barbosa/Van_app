/**
 * Medidas do sistema de design — independentes de paleta (Bloco B8).
 *
 * TOQUE_MIN é a restrição mais importante do app (CLAUDE.md §8): o motorista
 * está dirigindo, todo alvo de toque tem pelo menos 56dp. TOQUE_GRANDE (72dp,
 * Bloco B7) é para botão de diálogo e para a ação primária do card de parada.
 */
export const TOQUE_MIN = 56;
export const TOQUE_GRANDE = 72;

export const espacamento = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
} as const;

export const raio = {
  sm: 10,
  md: 14,
  lg: 18,
  pilula: 999,
} as const;

/**
 * Escala tipográfica. **Piso de 13sp** — CLAUDE.md §8: a tela é lida sob sol
 * direto, em aparelho antigo.
 *
 * O B7 declarou esse piso mas não o fez valer: sobraram `fontSize: 12.5` no
 * `EstadoBadge`, `12` no `PillSync` e `11.5` na tela de finalizar, porque eram
 * números crus espalhados pelos `StyleSheet` em vez de vir daqui. O B8 fechou
 * isso por teste (`__tests__/tipografia.test.ts`), que varre os fontes do
 * Motorista e dos componentes compartilhados e reprova qualquer `fontSize`
 * numérico literal — o valor tem que sair desta escala.
 *
 * `numero` é maior que `destaque` porque a ordem da parada é o dado que o
 * motorista casa com a lista de papel/memória dele, de relance.
 */
export const tipografia = {
  numero: 26,
  destaque: 22,
  titulo: 19,
  subtitulo: 17,
  corpo: 15,
  endereco: 14,
  legenda: 13,
} as const;

/**
 * Pesos nomeados. Evita `fontWeight: "700"` espalhado e, principalmente, evita
 * o peso 500/600 em aparelho Android antigo: sem a família variável instalada,
 * o sistema arredonda 500/600 para regular e a hierarquia que se desenhou no
 * emulador desaparece no aparelho do motorista. Só regular e bold de verdade.
 */
export const peso = {
  normal: "400",
  forte: "700",
} as const;

/** Rótulo do estado do aluno em letras maiúsculas espaçadas — o selo virou
 * texto com fundo, e `letterSpacing` é o que o mantém legível em caixa alta. */
export const ESPACO_LETRA_SELO = 0.6;
