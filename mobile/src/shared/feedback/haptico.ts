/**
 * Retorno tátil (Bloco B7).
 *
 * Até o B6 o único sinal de que um toque tinha pego era `opacity: 0.85` no
 * estado pressed. Isso obriga o motorista a OLHAR a tela para saber se
 * registrou — exatamente o que o CLAUDE.md §8 existe para evitar. Ele está
 * dirigindo; a confirmação precisa chegar pela mão.
 *
 * Best-effort por decisão: em aparelho sem motor de vibração, com a vibração
 * desligada nas configurações do sistema, ou se o módulo nativo não carregar
 * (Expo Go em certos aparelhos), a chamada falha silenciosamente. Nenhum fluxo
 * do app pode depender disto — é reforço, não canal primário.
 */
import * as Haptics from "expo-haptics";

function tentar(executar: () => Promise<unknown>): void {
  try {
    void executar().catch(() => undefined);
  } catch {
    // Módulo indisponível — segue sem háptico.
  }
}

/** Ação registrada: confirmação de diálogo, Checkin, Checkout. */
export function hapticoAcao(): void {
  tentar(() => Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium));
}

/** Evento saiu da fila e o servidor aceitou. */
export function hapticoSucesso(): void {
  tentar(() => Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success));
}

/** 409 de domínio, bloqueio do §7.2, falha definitiva. Padrão distinto do de
 * sucesso de propósito: "deu errado" precisa ser reconhecível sem olhar. */
export function hapticoErro(): void {
  tentar(() => Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error));
}
