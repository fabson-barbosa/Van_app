/** Tipos de navegação — uma única stack, ramificada por `role` (Bloco B5).
 * Arquivo separado pra `shared/notifications` poder navegar (toque em push)
 * sem importar `RootNavigator.tsx` inteiro. */
export type RootStackParamList = {
  Login: undefined;
  // Motorista (Bloco B4)
  RotaDoDia: undefined;
  Viagem: { viagemId: string };
  FinalizarViagem: { viagemId: string };
  // Responsável (Bloco B5)
  ListaFilhos: undefined;
  AcompanharFilho: { alunoId: string; nome?: string };
  HistoricoFilho: { alunoId: string; nome?: string };
};
