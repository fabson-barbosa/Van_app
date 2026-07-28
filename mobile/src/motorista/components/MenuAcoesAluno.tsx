/**
 * Ações fora de ordem de um aluno — aberto pelo toque no `EstadoBadge`
 * (Bloco B7).
 *
 * Por que existe: a ação primária da rota vive no card de parada atual, e as
 * linhas da lista são consulta. Mas duas correções não seguem a sequência da
 * rota e precisam de um caminho:
 *
 * - **Desfazer chegada** (§4, `chegou` -> `aguardando`): o motorista apertou
 *   Cheguei no aluno errado. Sem isto ele fica preso — o push já saiu e o §7.2
 *   bloqueia o Cheguei seguinte enquanto a parada anterior estiver em `chegou`.
 * - **Marcar ausente a partir de `aguardando`** (§4): o responsável avisou de
 *   manhã que o aluno não vai hoje. O alvo está lá na frente da rota, não na
 *   parada atual.
 *
 * `a_bordo` e os terminais NÃO abrem menu (o badge nem fica tocável): desfazer
 * checkin tem janela de 60s e caminho próprio — a barra de undo —, e sair de
 * `entregue`/`ausente` não existe na máquina de estados.
 *
 * "Desfazer chegada" não abre diálogo de confirmação: abrir este menu já é o
 * primeiro dos dois toques, e é a saída de emergência — encher de atrito a
 * correção de um erro é o oposto do que o B7 está fazendo. "Marcar ausente"
 * abre, porque `ausente` é terminal e não tem volta.
 */
import React from "react";
import { Modal, StyleSheet, Text, View } from "react-native";

import { Botao56 } from "../../shared/components/Botao56";
import type { TripStudentEstado } from "../../shared/api/types";
import { cores, espacamento, raio, tipografia } from "../../shared/theme";

/** Estados em que o badge é tocável — fonte única, usada também pelas telas
 * para decidir se passam `onPress` ao `EstadoBadge`. */
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
  return (
    <Modal visible={visivel} transparent animationType="fade" onRequestClose={onFechar}>
      <View style={estilos.fundo}>
        <View style={estilos.cartao}>
          <Text style={estilos.nome} numberOfLines={1}>
            {nomeAluno}
          </Text>

          {estado === "chegou" ? (
            <Botao56
              titulo="Desfazer chegada"
              variante="secundario"
              tamanho="grande"
              onPress={onDesfazerChegada}
              estilo={estilos.acao}
              testID="acao-desfazer-chegada"
            />
          ) : null}

          <Botao56
            titulo="Marcar ausente"
            variante="destrutivo"
            tamanho="grande"
            onPress={onMarcarAusente}
            estilo={estilos.acao}
            testID="acao-marcar-ausente"
          />

          <Botao56
            titulo="Cancelar"
            variante="secundario"
            tamanho="grande"
            onPress={onFechar}
            estilo={estilos.acao}
          />
        </View>
      </View>
    </Modal>
  );
}

const estilos = StyleSheet.create({
  fundo: {
    flex: 1,
    backgroundColor: "rgba(16,35,30,0.55)",
    alignItems: "center",
    justifyContent: "center",
    padding: espacamento.xl,
  },
  cartao: {
    width: "100%",
    maxWidth: 380,
    backgroundColor: cores.cartao,
    borderRadius: raio.lg,
    padding: espacamento.xl,
    gap: espacamento.md,
  },
  nome: {
    fontSize: tipografia.destaque,
    fontWeight: "700",
    color: cores.tinta,
    textAlign: "center",
    marginBottom: espacamento.xs,
  },
  acao: {
    width: "100%",
  },
});
