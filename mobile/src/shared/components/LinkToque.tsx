/**
 * Ação textual secundária com alvo de toque de verdade (Bloco B7).
 *
 * O app usava `<Text onPress>` para "Estou atrasado", "Reordenar paradas",
 * "Ok" dos banners, "Voltar para a viagem" e "Sair". Um `Text` de 13sp tem
 * ~18dp de altura tocável — bem abaixo do piso de 56dp do CLAUDE.md §8 — e
 * `Text` sequer aceita `hitSlop` no React Native, então não dava pra corrigir
 * sem trocar o elemento.
 *
 * Para "Sair" e "Voltar" o alvo pequeno até protegia contra toque acidental,
 * mas "Estou atrasado" é ação de rota, usada em movimento, e o "Ok" de um
 * banner de conflito aparece quando algo já deu errado — os dois piores
 * momentos para exigir pontaria.
 */
import React from "react";
import { Pressable, StyleSheet, Text, type TextStyle } from "react-native";

import { TOQUE_MIN, espacamento, tipografia } from "../theme";

interface Props {
  titulo: string;
  onPress: () => void;
  cor: string;
  estiloTexto?: TextStyle;
  accessibilityLabel?: string;
  testID?: string;
}

export function LinkToque({
  titulo,
  onPress,
  cor,
  estiloTexto,
  accessibilityLabel,
  testID,
}: Props): React.JSX.Element {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel ?? titulo}
      testID={testID}
      onPress={onPress}
      hitSlop={12}
      style={({ pressed }) => [estilos.base, pressed && estilos.pressionado]}
    >
      <Text style={[estilos.texto, { color: cor }, estiloTexto]}>{titulo}</Text>
    </Pressable>
  );
}

const estilos = StyleSheet.create({
  base: {
    minHeight: TOQUE_MIN,
    justifyContent: "center",
    paddingHorizontal: espacamento.sm,
  },
  pressionado: {
    opacity: 0.6,
  },
  texto: {
    fontSize: tipografia.legenda,
    fontWeight: "700",
    textAlign: "center",
  },
});
