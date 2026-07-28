/** Mapa VIRTUAL (CLAUDE.md §2/§10): progresso por PARADA, nunca coordenada.
 * Uma bolinha por parada da rota; preenchidas = já percorridas, marcada com
 * borda = a parada do PRÓPRIO filho. Sem GPS, sem geometria — só contagem. */
import React from "react";
import { StyleSheet, Text, View } from "react-native";

import { cores, espacamento, raio } from "../../shared/theme";

interface Props {
  paradasTotais: number;
  paradasConcluidas: number;
  paradasRestantes: number;
}

export function BarraProgresso({ paradasTotais, paradasConcluidas, paradasRestantes }: Props): React.JSX.Element {
  const posicaoFilho = Math.max(0, paradasTotais - paradasRestantes - 1);
  const bolinhas = Array.from({ length: Math.max(paradasTotais, 1) }, (_, indice) => indice);

  return (
    <View>
      <View style={estilos.linha}>
        {bolinhas.map((indice) => (
          <View
            key={indice}
            style={[
              estilos.bolinha,
              indice < paradasConcluidas && estilos.bolinhaConcluida,
              indice === posicaoFilho && estilos.bolinhaFilho,
            ]}
          />
        ))}
      </View>
      <Text style={estilos.legenda}>
        {paradasRestantes === 0
          ? "A van está na parada do seu filho"
          : `Faltam ${paradasRestantes} parada${paradasRestantes === 1 ? "" : "s"} até a parada do seu filho`}
      </Text>
    </View>
  );
}

const estilos = StyleSheet.create({
  linha: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    flexWrap: "wrap",
  },
  bolinha: {
    width: 14,
    height: 14,
    borderRadius: raio.sm,
    backgroundColor: cores.linha2,
  },
  bolinhaConcluida: {
    backgroundColor: cores.marca,
  },
  bolinhaFilho: {
    borderWidth: 2,
    borderColor: cores.ambar,
  },
  legenda: {
    fontSize: 12.5,
    color: cores.esmaecido,
    marginTop: espacamento.sm,
  },
});
