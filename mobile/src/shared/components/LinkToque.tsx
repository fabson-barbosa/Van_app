/**
 * Ação textual secundária com alvo de toque de verdade (Bloco B7).
 *
 * O app usava `<Text onPress>` para "Estou atrasado", "Reordenar paradas", "Ok"
 * dos banners, "Voltar para a viagem" e "Sair". Um `Text` de 13sp tem ~18dp de
 * altura tocável — bem abaixo do piso de 56dp do CLAUDE.md §8 — e `Text` sequer
 * aceita `hitSlop` no React Native, então não dava para corrigir sem trocar o
 * elemento.
 *
 * Bloco B8: `cor` virou opcional. Quem não passa nada recebe `marca` da paleta
 * em vigor, o que faz o link funcionar nos dois temas sem cada tela repetir a
 * escolha. E o texto ganhou sublinhado: num app onde quase tudo é botão com
 * fundo, texto colorido solto não lê como alvo — sublinhar é o sinal mais
 * barato e universal de "isto é tocável".
 */
import React from "react";
import { Pressable, StyleSheet, Text, type TextStyle } from "react-native";

import { TOQUE_MIN, type Paleta, espacamento, peso, tipografia, useEstilos, useTema } from "../theme";

interface Props {
  titulo: string;
  onPress: () => void;
  /** Padrão: `marca` da paleta em vigor. */
  cor?: string;
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
  const { cores } = useTema();
  const estilos = useEstilos(criarEstilos, cores);

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel ?? titulo}
      testID={testID}
      onPress={onPress}
      hitSlop={12}
      style={({ pressed }) => [estilos.base, pressed && estilos.pressionado]}
    >
      <Text style={[estilos.texto, { color: cor ?? cores.marca }, estiloTexto]}>{titulo}</Text>
    </Pressable>
  );
}

const criarEstilos = (_cores: Paleta) =>
  StyleSheet.create({
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
      fontWeight: peso.forte,
      textAlign: "center",
      textDecorationLine: "underline",
    },
  });
