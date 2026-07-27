/**
 * Barra de ação do modo de reordenação (CLAUDE.md §8 — só alunos ainda em
 * 'aguardando'; as setas por linha estão em `AlunoRow.tsx`). Reordenar é
 * online-only (ver `shared/offline/queue.ts`) — "Concluir ordem" chama a
 * API direto; se não houver sinal, o erro aparece inline e o motorista pode
 * tentar de novo ou cancelar.
 */
import React from "react";
import { StyleSheet, View } from "react-native";

import { Botao56 } from "../../shared/components/Botao56";
import { espacamento } from "../../shared/theme";

interface Props {
  onConcluir: () => void;
  onCancelar: () => void;
  salvando: boolean;
}

export function ModoReordenar({ onConcluir, onCancelar, salvando }: Props): React.JSX.Element {
  return (
    <View style={estilos.base}>
      <Botao56
        titulo="Cancelar"
        variante="secundario"
        onPress={onCancelar}
        desabilitado={salvando}
        estilo={estilos.botao}
      />
      <Botao56
        titulo="Concluir ordem"
        variante="primario"
        onPress={onConcluir}
        carregando={salvando}
        estilo={estilos.botao}
      />
    </View>
  );
}

const estilos = StyleSheet.create({
  base: {
    flexDirection: "row",
    gap: espacamento.md,
    padding: espacamento.md,
  },
  botao: {
    flex: 1,
  },
});
