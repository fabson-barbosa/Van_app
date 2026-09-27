/**
 * Banner inline de mensagem (Bloco B8).
 *
 * A `ViagemScreen` tinha quatro blocos quase idênticos — erro de carregamento,
 * bloqueio do §7.2, conflito da fila, confirmação de atraso — cada um com seu
 * `View` + `Text` + `LinkToque` e seu par de estilos copiados. Quatro cópias de
 * um padrão significam quatro lugares para o próximo tom de cor divergir, e no
 * modo escuro isso multiplicaria por dois.
 *
 * Os banners são preferidos a `Alert` nativo desde o B7 por um motivo de domínio,
 * não estético: o §7.2 pede "forçar resolução na tela imediatamente", e um alerta
 * modal com um "Entendi" interrompe sem levar a lugar nenhum. O banner fica na
 * tela, junto do que precisa ser resolvido, e pode CITAR O CAMINHO.
 */
import React from "react";
import { StyleSheet, Text, View } from "react-native";

import { LinkToque } from "./LinkToque";
import { type Paleta, espacamento, peso, raio, tipografia, useEstilos, useTema } from "../theme";

export type TomBanner = "erro" | "aviso" | "ok" | "info";

interface Props {
  tom: TomBanner;
  mensagem: string;
  /** Ação à direita. Sem ela o banner é só informativo. */
  acao?: { titulo: string; onPress: () => void; accessibilityLabel?: string };
  /** Até onde a mensagem pode crescer antes de truncar. */
  maxLinhas?: number;
  testID?: string;
}

function coresDoTom(cores: Paleta, tom: TomBanner): { fundo: string; borda: string; texto: string } {
  switch (tom) {
    case "erro":
      return { fundo: cores.perigoSuave, borda: cores.perigoBorda, texto: cores.perigo };
    case "aviso":
      return { fundo: cores.ambarSuave, borda: cores.ambarBorda, texto: cores.ambar };
    case "ok":
      return { fundo: cores.marcaSuave, borda: cores.marcaBorda, texto: cores.marca };
    case "info":
      return { fundo: cores.infoSuave, borda: cores.infoBorda, texto: cores.info };
  }
}

export function Banner({ tom, mensagem, acao, maxLinhas = 3, testID }: Props): React.JSX.Element {
  const { cores } = useTema();
  const estilos = useEstilos(criarEstilos, cores);
  const { fundo, borda, texto } = coresDoTom(cores, tom);

  return (
    <View style={[estilos.base, { backgroundColor: fundo, borderColor: borda }]} testID={testID}>
      <Text style={[estilos.mensagem, { color: texto }]} numberOfLines={maxLinhas}>
        {mensagem}
      </Text>
      {acao ? (
        <LinkToque
          titulo={acao.titulo}
          cor={texto}
          accessibilityLabel={acao.accessibilityLabel}
          onPress={acao.onPress}
        />
      ) : null}
    </View>
  );
}

const criarEstilos = (_cores: Paleta) =>
  StyleSheet.create({
    base: {
      flexDirection: "row",
      alignItems: "center",
      gap: espacamento.sm,
      marginHorizontal: espacamento.lg,
      marginTop: espacamento.sm,
      borderRadius: raio.md,
      borderWidth: 1,
      paddingVertical: espacamento.sm,
      paddingLeft: espacamento.md,
      paddingRight: espacamento.xs,
    },
    mensagem: {
      flex: 1,
      fontSize: tipografia.legenda,
      fontWeight: peso.forte,
      lineHeight: tipografia.legenda * 1.35,
    },
  });
