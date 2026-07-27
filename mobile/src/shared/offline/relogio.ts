/**
 * Carimbos de relógio do aparelho — insumos da reconciliação do servidor
 * (`backend/app/services/reconciliacao.py`, Bloco B4).
 *
 * O app NUNCA tenta corrigir o próprio relógio nem decidir "o que realmente
 * aconteceu quando" — isso é responsabilidade do servidor, que tem os dois
 * lados (device_timestamp do toque + device_enviado_em do envio) pra
 * calcular o offset. Aqui só carimbamos os dois instantes, fielmente.
 */

/** Instante do TOQUE — carimbar assim que a ação do motorista acontece,
 * antes de qualquer enfileiramento ou espera de rede. */
export function agoraISO(): string {
  return new Date().toISOString();
}
