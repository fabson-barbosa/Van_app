/**
 * Estado do aluno sempre visível sem abrir nada (CLAUDE.md §8).
 *
 * Bloco B7 — o badge virou também o CANAL DE AÇÕES FORA DE ORDEM. Com a ação
 * primária concentrada no card de parada atual, é por aqui que o motorista
 * alcança o que não está na sequência da rota: desfazer uma chegada registrada
 * no aluno errado, ou marcar ausente alguém lá na frente porque o responsável
 * avisou de manhã (caso previsto no §4, `aguardando` -> `ausente`).
 *
 * Um selo não parece um botão — é o custo da decisão de não poluir a linha com
 * um terceiro alvo. Duas coisas compensam isso: o sufixo "▾", que só aparece
 * quando o badge é tocável, e a mensagem do bloqueio §7.2, que cita o caminho
 * pelo nome ("toque no selo Chegou de Fulano").
 *
 * `hitSlop` não é cosmético aqui: o badge tem ~24dp de altura, e sem ele o
 * alvo violaria o piso de 56dp do §8.
 */
import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

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

/** Vertical necessário para o alvo chegar a TOQUE_MIN (56dp) a partir da
 * altura natural do badge (~24dp com o padding abaixo). */
const HITSLOP_TOCAVEL = { top: 16, bottom: 16, left: 12, right: 12 };

interface Props {
  estado: TripStudentEstado;
  /** Quando presente, o badge vira alvo e ganha o sufixo "▾". */
  onPress?: () => void;
  /** Nome do aluno — só para o rótulo de acessibilidade. */
  nomeAluno?: string;
}

export function EstadoBadge({ estado, onPress, nomeAluno }: Props): React.JSX.Element {
  const { fundo, texto } = CORES[estado];

  const conteudo = (
    <View style={[estilos.base, { backgroundColor: fundo }, onPress != null && estilos.tocavel]}>
      <Text style={[estilos.texto, { color: texto }]}>
        {ROTULOS[estado]}
        {onPress != null ? " ▾" : ""}
      </Text>
    </View>
  );

  if (onPress == null) return conteudo;

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={
        nomeAluno
          ? `${ROTULOS[estado]} — abrir ações de ${nomeAluno}`
          : `${ROTULOS[estado]} — abrir ações`
      }
      onPress={onPress}
      hitSlop={HITSLOP_TOCAVEL}
      style={({ pressed }) => (pressed ? estilos.pressionado : undefined)}
    >
      {conteudo}
    </Pressable>
  );
}

const estilos = StyleSheet.create({
  base: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: raio.sm,
    alignSelf: "flex-start",
  },
  tocavel: {
    borderWidth: 1,
    borderColor: cores.linha2,
  },
  pressionado: {
    opacity: 0.7,
  },
  texto: {
    fontSize: 12.5,
    fontWeight: "700",
  },
});
