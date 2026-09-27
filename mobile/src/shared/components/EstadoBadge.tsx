/**
 * Estado do aluno sempre visível sem abrir nada (CLAUDE.md §8).
 *
 * Bloco B7 — o badge virou também o CANAL DE AÇÕES FORA DE ORDEM. Com a ação
 * primária concentrada no card de parada atual, é por aqui que o motorista
 * alcança o que não está na sequência da rota: desfazer uma chegada registrada
 * no aluno errado, ou marcar ausente alguém lá na frente porque o responsável
 * avisou de manhã (caso previsto no §4, `aguardando` -> `ausente`).
 *
 * Bloco B8 — três correções:
 *
 * 1. **13sp, não 12,5.** O §8 fixa 13sp como piso e este componente era o
 *    exemplo mais visível de quem não cumpria. Como compensação de espaço o
 *    rótulo virou caixa alta com `letterSpacing`, que ocupa menos altura e lê
 *    melhor de relance que minúsculas no mesmo tamanho.
 * 2. **Fundo opaco por paleta.** O selo "Aguardando" usava `rgba(16,35,30,0.10)`
 *    — translúcido, logo sem razão de contraste demonstrável, e sobre fundo
 *    escuro viraria um cinza quase invisível. Agora é `neutroSuave`.
 * 3. **O "▾" virou ponto.** A seta sugeria "expandir uma lista"; o que abre é um
 *    menu de correção. Um marcador redondo na frente do rótulo diz "tem algo
 *    aqui" sem prometer a mecânica errada, e sobra largura para o rótulo.
 *
 * `hitSlop` não é cosmético: o selo tem ~26dp de altura e sem ele o alvo
 * violaria o piso de 56dp do §8.
 */
import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import type { TripStudentEstado } from "../api/types";
import { ESPACO_LETRA_SELO, type Paleta, peso, raio, tipografia, useEstilos, useTema } from "../theme";

const ROTULOS: Record<TripStudentEstado, string> = {
  aguardando: "Aguardando",
  chegou: "Chegou",
  a_bordo: "A bordo",
  entregue: "Entregue",
  ausente: "Ausente",
};

function paletaDoEstado(cores: Paleta, estado: TripStudentEstado): { fundo: string; texto: string; borda: string } {
  switch (estado) {
    case "aguardando":
      return { fundo: cores.neutroSuave, texto: cores.esmaecido, borda: cores.linha2 };
    case "chegou":
      return { fundo: cores.infoSuave, texto: cores.info, borda: cores.infoBorda };
    case "a_bordo":
    case "entregue":
      return { fundo: cores.marcaSuave, texto: cores.marca, borda: cores.marcaBorda };
    case "ausente":
      return { fundo: cores.ambarSuave, texto: cores.ambar, borda: cores.ambarBorda };
  }
}

/** Vertical necessário para o alvo chegar a TOQUE_MIN (56dp) a partir da
 * altura natural do selo. */
const HITSLOP_TOCAVEL = { top: 15, bottom: 15, left: 12, right: 12 };

interface Props {
  estado: TripStudentEstado;
  /** Quando presente, o selo vira alvo e ganha o marcador de ação. */
  onPress?: () => void;
  /** Nome do aluno — só para o rótulo de acessibilidade. */
  nomeAluno?: string;
}

export function EstadoBadge({ estado, onPress, nomeAluno }: Props): React.JSX.Element {
  const { cores } = useTema();
  const estilos = useEstilos(criarEstilos, cores);
  const { fundo, texto, borda } = paletaDoEstado(cores, estado);
  const tocavel = onPress != null;

  const conteudo = (
    <View style={[estilos.base, { backgroundColor: fundo, borderColor: borda }]}>
      {tocavel ? <View style={[estilos.marcador, { backgroundColor: texto }]} /> : null}
      <Text style={[estilos.texto, { color: texto }]}>{ROTULOS[estado].toUpperCase()}</Text>
    </View>
  );

  if (!tocavel) return conteudo;

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={
        nomeAluno ? `${ROTULOS[estado]} — abrir ações de ${nomeAluno}` : `${ROTULOS[estado]} — abrir ações`
      }
      onPress={onPress}
      hitSlop={HITSLOP_TOCAVEL}
      style={({ pressed }) => (pressed ? estilos.pressionado : undefined)}
    >
      {conteudo}
    </Pressable>
  );
}

const criarEstilos = (_cores: Paleta) =>
  StyleSheet.create({
    base: {
      flexDirection: "row",
      alignItems: "center",
      gap: 6,
      paddingHorizontal: 10,
      paddingVertical: 5,
      borderRadius: raio.pilula,
      borderWidth: 1,
      alignSelf: "flex-start",
    },
    marcador: {
      width: 6,
      height: 6,
      borderRadius: raio.pilula,
    },
    texto: {
      fontSize: tipografia.legenda,
      fontWeight: peso.forte,
      letterSpacing: ESPACO_LETRA_SELO,
    },
    pressionado: {
      opacity: 0.65,
    },
  });
