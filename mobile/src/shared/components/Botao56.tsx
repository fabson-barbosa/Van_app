/**
 * Botão com alvo de toque garantido (CLAUDE.md §8 — 56dp; 72dp em diálogo).
 *
 * Bloco B8 — duas mudanças de fundo:
 *
 * 1. **Cores vêm da paleta em vigor, não de constantes.** O mapa antigo tinha
 *    `primario: "#ffffff"` como cor de texto, cravado no módulo. No tema escuro
 *    o preenchimento verde clareia e texto branco sobre ele reprova AA. Agora o
 *    primeiro plano de cada preenchimento sai de `sobreMarca`/`sobrePerigo`, que
 *    cada paleta define para si (ver `theme/paleta.ts`).
 * 2. **`android_ripple`.** O feedback de toque era `opacity: 0.85`, que em
 *    aparelho antigo aparece depois do dedo já ter saído. O ripple nativo é
 *    desenhado pelo próprio Android, no ponto do toque, sem passar pela ponte —
 *    é o retorno visual mais rápido disponível, e vale num app usado em
 *    movimento. O háptico e o som (`shared/feedback`) seguem sendo o canal que
 *    não exige olhar.
 */
import React from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View, ViewStyle } from "react-native";

import {
  TOQUE_GRANDE,
  TOQUE_MIN,
  type Paleta,
  espacamento,
  peso,
  raio,
  tipografia,
  useEstilos,
  useTema,
} from "../theme";

type Variante = "primario" | "secundario" | "perigo" | "destrutivo" | "fantasma";
type Tamanho = "min" | "grande";

interface Props {
  titulo: string;
  onPress: () => void;
  variante?: Variante;
  tamanho?: Tamanho;
  desabilitado?: boolean;
  carregando?: boolean;
  /** Linha secundária dentro do botão (ex.: endereço da parada atual). */
  detalhe?: string | null;
  estilo?: ViewStyle;
  testID?: string;
  accessibilityLabel?: string;
}

function fundoDe(cores: Paleta, variante: Variante): string {
  switch (variante) {
    case "primario":
      return cores.marca;
    case "secundario":
      return cores.cartao;
    case "perigo":
      return cores.perigoSuave;
    case "destrutivo":
      return cores.perigoForte;
    case "fantasma":
      return "transparent";
  }
}

function textoDe(cores: Paleta, variante: Variante): string {
  switch (variante) {
    case "primario":
      return cores.sobreMarca;
    case "secundario":
      return cores.tinta;
    case "perigo":
      return cores.perigo;
    case "destrutivo":
      return cores.sobrePerigo;
    case "fantasma":
      return cores.esmaecido;
  }
}

export function Botao56({
  titulo,
  onPress,
  variante = "primario",
  tamanho = "min",
  desabilitado = false,
  carregando = false,
  detalhe,
  estilo,
  testID,
  accessibilityLabel,
}: Props): React.JSX.Element {
  const { cores } = useTema();
  const estilos = useEstilos(criarEstilos, cores);
  const inativo = desabilitado || carregando;
  const corTexto = textoDe(cores, variante);

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel ?? titulo}
      accessibilityState={{ disabled: inativo }}
      testID={testID}
      onPress={inativo ? undefined : onPress}
      android_ripple={inativo ? undefined : { color: cores.overlay, foreground: true }}
      style={({ pressed }) => [
        estilos.base,
        { minHeight: tamanho === "grande" ? TOQUE_GRANDE : TOQUE_MIN },
        { backgroundColor: fundoDe(cores, variante) },
        variante === "secundario" && estilos.bordaSecundario,
        inativo && estilos.inativo,
        pressed && !inativo && estilos.pressionado,
        estilo,
      ]}
    >
      {carregando ? (
        <ActivityIndicator color={corTexto} />
      ) : (
        <View style={estilos.rotulo}>
          <Text style={[estilos.texto, { color: corTexto }]} numberOfLines={1}>
            {titulo}
          </Text>
          {detalhe ? (
            <Text style={[estilos.detalhe, { color: corTexto }]} numberOfLines={1}>
              {detalhe}
            </Text>
          ) : null}
        </View>
      )}
    </Pressable>
  );
}

const criarEstilos = (cores: Paleta) =>
  StyleSheet.create({
    base: {
      borderRadius: raio.md,
      alignItems: "center",
      justifyContent: "center",
      paddingHorizontal: espacamento.lg,
      overflow: "hidden", // contém o ripple dentro do raio da borda
    },
    bordaSecundario: {
      borderWidth: 1,
      // `bordaAcao`, não `linha2`: é a borda que DIZ onde o botão está (o
      // preenchimento `cartao` sobre `papel` difere por ~1,07:1). Ver
      // `theme/__tests__/contraste.test.ts`.
      borderColor: cores.bordaAcao,
    },
    inativo: {
      opacity: 0.45,
    },
    pressionado: {
      // Sutil de propósito: o sinal forte de toque é o ripple nativo + háptico.
      opacity: 0.9,
    },
    rotulo: {
      alignItems: "center",
    },
    texto: {
      fontSize: tipografia.corpo,
      fontWeight: peso.forte,
      textAlign: "center",
    },
    detalhe: {
      fontSize: tipografia.legenda,
      fontWeight: peso.normal,
      textAlign: "center",
      marginTop: 2,
      opacity: 0.85,
    },
  });
