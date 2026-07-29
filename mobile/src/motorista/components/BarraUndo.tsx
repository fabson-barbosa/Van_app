/**
 * Undo de 30s do Checkin (CLAUDE.md §8) — a janela do SERVIDOR é 60s
 * (tolerância a latência/fila offline), mas a UI só oferece 30s pra não
 * incentivar o motorista a "corrigir" depois de a van já ter saído do lugar.
 *
 * Bloco B7: o prazo agora vem de `expiraEm` (instante absoluto, guardado em
 * `state/undoCheckin.ts`), não de um contador interno. Remontar o componente
 * — voltar de outra tela, o Android recriar a view — não devolve mais tempo
 * que já passou.
 */
import React, { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { TOQUE_MIN, cores, espacamento, raio, tipografia } from "../../shared/theme";

interface Props {
  nomeAluno: string;
  /** Instante absoluto (ms) em que a oferta expira. */
  expiraEm: number;
  onDesfazer: () => void;
  onExpirar: () => void;
}

function segundosRestantes(expiraEm: number): number {
  return Math.max(0, Math.ceil((expiraEm - Date.now()) / 1000));
}

export function BarraUndo({ nomeAluno, expiraEm, onDesfazer, onExpirar }: Props): React.JSX.Element {
  const [restante, setRestante] = useState(() => segundosRestantes(expiraEm));

  useEffect(() => {
    const intervalo = setInterval(() => {
      const agora = segundosRestantes(expiraEm);
      setRestante(agora);
      if (agora <= 0) {
        clearInterval(intervalo);
        onExpirar();
      }
    }, 1000);
    return () => clearInterval(intervalo);
    // `onExpirar` é recriado a cada render da tela; incluí-lo reiniciaria o
    // intervalo o tempo todo. `expiraEm` é a identidade real desta barra.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expiraEm]);

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
    marginBottom: espacamento.sm,
  },
  texto: {
    flex: 1,
    color: "#ffffff",
    fontSize: tipografia.legenda,
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
