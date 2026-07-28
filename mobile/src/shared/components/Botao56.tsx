/**
 * Botão com alvo de toque mínimo garantido (CLAUDE.md §8 — 56dp).
 *
 * `tamanho="grande"` (72dp, Bloco B7) é para os botões de diálogo: confirmar
 * algo irreversível com a van parada em fila dupla pede mais que o piso.
 *
 * `variante="destrutivo"` é fundo VERMELHO SÓLIDO, distinto de `perigo`
 * (vermelho claro, peso de ação terciária — é o "Finalizar viagem" da lista,
 * não o "Marcar ausente" de um diálogo).
 */
import React from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, ViewStyle } from "react-native";

import { TOQUE_GRANDE, TOQUE_MIN, cores, raio, tipografia } from "../theme";

type Variante = "primario" | "secundario" | "perigo" | "destrutivo" | "fantasma";
type Tamanho = "min" | "grande";

interface Props {
  titulo: string;
  onPress: () => void;
  variante?: Variante;
  tamanho?: Tamanho;
  desabilitado?: boolean;
  carregando?: boolean;
  estilo?: ViewStyle;
  testID?: string;
}

const FUNDOS: Record<Variante, string> = {
  primario: cores.marca,
  secundario: cores.cartao,
  perigo: cores.perigoSuave,
  destrutivo: cores.perigoForte,
  fantasma: "transparent",
};

const TEXTOS: Record<Variante, string> = {
  primario: "#ffffff",
  secundario: cores.tinta,
  perigo: cores.perigo,
  destrutivo: "#ffffff",
  fantasma: cores.esmaecido,
};

export function Botao56({
  titulo,
  onPress,
  variante = "primario",
  tamanho = "min",
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
        { minHeight: tamanho === "grande" ? TOQUE_GRANDE : TOQUE_MIN },
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
