/**
 * Ações fora de ordem de um aluno — aberto pelo toque no `EstadoBadge` (B7).
 *
 * Por que existe: a ação primária da rota vive no card de parada atual, e as
 * linhas da lista são consulta. Mas duas correções não seguem a sequência da rota
 * e precisam de um caminho:
 *
 * - **Desfazer chegada** (§4, `chegou` -> `aguardando`): o motorista apertou
 *   Cheguei no aluno errado. Sem isto ele fica preso — o push já saiu e o §7.2
 *   bloqueia o Cheguei seguinte enquanto a parada anterior estiver em `chegou`.
 * - **Marcar ausente a partir de `aguardando`** (§4): o responsável avisou de
 *   manhã que o aluno não vai hoje. O alvo está lá na frente da rota, não na
 *   parada atual.
 *
 * `a_bordo` e os terminais NÃO abrem menu (o selo nem fica tocável): desfazer
 * checkin tem janela de 60s e caminho próprio — a barra de undo —, e sair de
 * `entregue`/`ausente` não existe na máquina de estados.
 *
 * "Desfazer chegada" não abre diálogo de confirmação: abrir este menu já é o
 * primeiro dos dois toques, e é a saída de emergência — encher de atrito a
 * correção de um erro é o oposto do que estas regras existem para fazer.
 * "Marcar ausente" abre, porque `ausente` é terminal e não tem volta.
 *
 * Bloco B8 — virou folha inferior em vez de caixa centrada. Três razões, todas
 * do §8: o menu nasce de um toque no selo da LINHA, e uma caixa no centro da tela
 * desconecta causa de efeito; a zona alcançável pelo polegar é embaixo; e as duas
 * ações passaram a ter pesos visuais distintos (correção neutra, ausente
 * destrutivo), o que a pilha de três botões idênticos não mostrava.
 */
import React from "react";
import { Modal, Pressable, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Botao56 } from "../../shared/components/Botao56";
import type { TripStudentEstado } from "../../shared/api/types";
import {
  ESPACO_LETRA_SELO,
  type Paleta,
  espacamento,
  peso,
  raio,
  tipografia,
  useEstilos,
  useTema,
} from "../../shared/theme";

/** Estados em que o selo é tocável — fonte única, usada também pelas telas para
 * decidir se passam `onPress` ao `EstadoBadge`. */
export function temAcoesForaDeOrdem(estado: TripStudentEstado): boolean {
  return estado === "aguardando" || estado === "chegou";
}

interface Props {
  visivel: boolean;
  nomeAluno: string;
  estado: TripStudentEstado;
  onDesfazerChegada: () => void;
  onMarcarAusente: () => void;
  onFechar: () => void;
}

export function MenuAcoesAluno({
  visivel,
  nomeAluno,
  estado,
  onDesfazerChegada,
  onMarcarAusente,
  onFechar,
}: Props): React.JSX.Element {
  const { cores } = useTema();
  const estilos = useEstilos(criarEstilos, cores);
  const insets = useSafeAreaInsets();

  return (
    <Modal visible={visivel} transparent animationType="slide" statusBarTranslucent onRequestClose={onFechar}>
      <View style={estilos.fundo}>
        {/* Toque fora fecha — mesmo efeito do Voltar do Android, nunca confirma. */}
        <Pressable
          style={estilos.areaFora}
          accessibilityRole="button"
          accessibilityLabel="Fechar ações"
          onPress={onFechar}
        />

        <View style={[estilos.folha, { paddingBottom: espacamento.lg + insets.bottom }]}>
          <View style={estilos.alca} />

          <Text style={estilos.secao}>AÇÕES FORA DE ORDEM</Text>
          <Text style={estilos.nome} numberOfLines={1}>
            {nomeAluno}
          </Text>

          <View style={estilos.acoes}>
            {estado === "chegou" ? (
              <Botao56
                titulo="Desfazer chegada"
                variante="secundario"
                tamanho="grande"
                onPress={onDesfazerChegada}
                testID="acao-desfazer-chegada"
              />
            ) : null}

            <Botao56
              titulo="Marcar ausente"
              variante="destrutivo"
              tamanho="grande"
              onPress={onMarcarAusente}
              testID="acao-marcar-ausente"
            />

            <Botao56 titulo="Cancelar" variante="fantasma" tamanho="grande" onPress={onFechar} />
          </View>
        </View>
      </View>
    </Modal>
  );
}

const criarEstilos = (cores: Paleta) =>
  StyleSheet.create({
    fundo: {
      flex: 1,
      backgroundColor: cores.overlay,
      justifyContent: "flex-end",
    },
    areaFora: {
      flex: 1,
    },
    folha: {
      backgroundColor: cores.cartao,
      borderTopLeftRadius: raio.lg,
      borderTopRightRadius: raio.lg,
      paddingTop: espacamento.sm,
      paddingHorizontal: espacamento.lg,
    },
    alca: {
      width: 36,
      height: 4,
      borderRadius: raio.pilula,
      backgroundColor: cores.linha2,
      alignSelf: "center",
      marginBottom: espacamento.lg,
    },
    secao: {
      fontSize: tipografia.legenda,
      fontWeight: peso.forte,
      letterSpacing: ESPACO_LETRA_SELO,
      color: cores.dica,
    },
    nome: {
      fontSize: tipografia.destaque,
      fontWeight: peso.forte,
      color: cores.tinta,
      marginTop: espacamento.xs,
    },
    acoes: {
      gap: espacamento.md,
      marginTop: espacamento.lg,
    },
  });
