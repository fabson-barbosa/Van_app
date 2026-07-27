/** Botão com alvo de toque mínimo garantido (CLAUDE.md §8 — 56dp). */
import React from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, ViewStyle } from "react-native";

import { TOQUE_MIN, cores, raio, tipografia } from "../theme";

type Variante = "primario" | "secundario" | "perigo" | "fantasma";

interface Props {
  titulo: string;
  onPress: () => void;
  variante?: Variante;
  desabilitado?: boolean;
  carregando?: boolean;
  estilo?: ViewStyle;
  testID?: string;
}

const FUNDOS: Record<Variante, string> = {
  primario: cores.marca,
  secundario: cores.cartao,
  perigo: cores.perigoSuave,
  fantasma: "transparent",
};

const TEXTOS: Record<Variante, string> = {
  primario: "#ffffff",
  secundario: cores.tinta,
  perigo: cores.perigo,
  fantasma: cores.esmaecido,
};

export function Botao56({
  titulo,
  onPress,
  variante = "primario",
  desabilitado = false,
  carregando = false,
  estilo,
  testID,
}: Props): React.JSX.Element {
  const inativo = desabilitado || carregando;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled: inativo }}
      testID={testID}
      onPress={inativo ? undefined : onPress}
      style={({ pressed }) => [
        estilos.base,
        { backgroundColor: FUNDOS[variante] },
        variante === "secundario" && estilos.bordaSecundario,
        inativo && estilos.inativo,
        pressed && !inativo && estilos.pressionado,
        estilo,
      ]}
    >
      {carregando ? (
        <ActivityIndicator color={TEXTOS[variante]} />
      ) : (
        <Text style={[estilos.texto, { color: TEXTOS[variante] }]} numberOfLines={1}>
          {titulo}
        </Text>
      )}
    </Pressable>
  );
}

const estilos = StyleSheet.create({
  base: {
    minHeight: TOQUE_MIN,
    borderRadius: raio.md,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 18,
  },
  bordaSecundario: {
    borderWidth: 1,
    borderColor: cores.linha2,
  },
  inativo: {
    opacity: 0.5,
  },
  pressionado: {
    opacity: 0.85,
  },
  texto: {
    fontSize: tipografia.corpo,
    fontWeight: "700",
  },
});
