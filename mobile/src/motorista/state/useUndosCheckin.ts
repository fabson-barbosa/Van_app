/**
 * Assina o registro de undos de Checkin (`state/undoCheckin.ts`).
 *
 * O registro é estado de módulo — é o que faz o undo sobreviver a navegar para
 * "Finalizar viagem" e voltar. Este hook só reflete esse estado na tela.
 */
import { useEffect, useState } from "react";

import { assinarUndos, listarUndosVivos, type UndoCheckin } from "./undoCheckin";

export function useUndosCheckin(viagemId: string): UndoCheckin[] {
  const [undos, setUndos] = useState<UndoCheckin[]>(() => listarUndosVivos(viagemId));

  useEffect(() => {
    const atualizar = () => setUndos(listarUndosVivos(viagemId));
    atualizar();
    return assinarUndos(atualizar);
  }, [viagemId]);

  return undos;
}
