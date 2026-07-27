/**
 * Undo de 30s do Checkin (CLAUDE.md §8) — a janela do SERVIDOR é 60s
 * (tolerância a latência/fila offline), mas a UI só oferece 30s pra não
 * incentivar o motorista a "corrigir" depois de a van já ter saído do lugar.
 *
 * Monte com uma `key` que mude por aluno/tentativa (ex.: `tripStudentId`) —
 * o timer é interno e reinicia sozinho a cada montagem.
 */
import React, { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { TOQUE_MIN, cores, espacamento, raio } from "../../shared/theme";

const DURACAO_SEGUNDOS = 30;

interface Props {
  nomeAluno: string;
  onDesfazer: () => void;
  onExpirar: () => void;
}

export function BarraUndo({ nomeAluno, onDesfazer, onExpirar }: Props): React.JSX.Element {
  const [restante, setRestante] = useState(DURACAO_SEGUNDOS);

  useEffect(() => {
    const intervalo = setInterval(() => {
      setRestante((atual) => {
        if (atual <= 1) {
          clearInterval(intervalo);
          onExpirar();
          return 0;
        }
        return atual - 1;
      });
    }, 1000);
    return () => clearInterval(intervalo);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <View style={estilos.base}>
      <Text style={estilos.texto} numberOfLines={1}>
        Checkin de {nomeAluno} · desfazer em {restante}s
      </Text>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`Desfazer checkin de ${nomeAluno}`}
        onPress={onDesfazer}
        style={estilos.botao}
        hitSlop={8}
      >
        <Text style={estilos.botaoTexto}>Desfazer</Text>
      </Pressable>
    </View>
  );
}

const estilos = StyleSheet.create({
  base: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: cores.tinta,
    borderRadius: raio.md,
    paddingLeft: espacamento.lg,
    paddingRight: espacamento.xs,
    marginBottom: espacamento.md,
  },
  texto: {
    flex: 1,
    color: "#ffffff",
    fontSize: 13,
    fontWeight: "600",
  },
  botao: {
    minWidth: 100,
    minHeight: TOQUE_MIN,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: espacamento.md,
  },
  botaoTexto: {
    color: cores.sol,
    fontSize: 14,
    fontWeight: "700",
  },
});
