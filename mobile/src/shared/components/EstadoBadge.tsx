/** Estado do aluno sempre visível sem abrir nada (CLAUDE.md §8). */
import React from "react";
import { StyleSheet, Text, View } from "react-native";

import type { TripStudentEstado } from "../api/types";
import { cores, raio } from "../theme";

const ROTULOS: Record<TripStudentEstado, string> = {
  aguardando: "Aguardando",
  chegou: "Chegou",
  a_bordo: "A bordo",
  entregue: "Entregue",
  ausente: "Ausente",
};

const CORES: Record<TripStudentEstado, { fundo: string; texto: string }> = {
  aguardando: { fundo: cores.linha, texto: cores.esmaecido },
  chegou: { fundo: cores.infoSuave, texto: cores.info },
  a_bordo: { fundo: cores.marcaSuave, texto: cores.marca },
  entregue: { fundo: cores.marcaSuave, texto: cores.marca },
  ausente: { fundo: cores.ambarSuave, texto: cores.ambar },
};

export function EstadoBadge({ estado }: { estado: TripStudentEstado }): React.JSX.Element {
  const { fundo, texto } = CORES[estado];
  return (
    <View style={[estilos.base, { backgroundColor: fundo }]}>
      <Text style={[estilos.texto, { color: texto }]}>{ROTULOS[estado]}</Text>
    </View>
  );
}

const estilos = StyleSheet.create({
  base: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: raio.sm,
    alignSelf: "flex-start",
  },
  texto: {
    fontSize: 11.5,
    fontWeight: "700",
  },
});
