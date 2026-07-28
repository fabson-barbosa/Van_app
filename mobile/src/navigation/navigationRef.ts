/** Ref global de navegação — permite navegar a partir de fora da árvore de
 * componentes (ex.: toque numa notificação, tratado em
 * `shared/notifications`, que roda antes de qualquer tela existir). */
import { createNavigationContainerRef } from "@react-navigation/native";

import type { RootStackParamList } from "./types";

export const navigationRef = createNavigationContainerRef<RootStackParamList>();

export function navegarParaFilho(alunoId: string, nome?: string): void {
  if (!navigationRef.isReady()) return;
  navigationRef.navigate("AcompanharFilho", { alunoId, nome });
}
