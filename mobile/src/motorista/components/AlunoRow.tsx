/**
 * Uma linha por aluno — CLAUDE.md §8: estado sempre visível sem abrir nada.
 *
 * Bloco B7 — a linha PERDEU os botões de ação. Antes ela carregava o botão
 * primário (Cheguei/Checkin/Checkout) e mais um "Ausente" a 12dp dele: dois
 * alvos competindo pelo polegar, numa van em movimento, sendo que um deles é
 * irreversível. O §8 pede "uma ação por linha" e a linha tinha duas. A ação
 * primária passou para o card do rodapé; aqui sobrou consulta + o selo, que abre
 * as ações fora de ordem (ver `MenuAcoesAluno`).
 *
 * Bloco B8 — a lista é uma LISTA, não uma pilha de cartões:
 *
 * - **A ordem da parada ganhou coluna própria**, à esquerda, alinhada entre as
 *   linhas. É o número que o motorista casa com a sequência que tem na cabeça (ou
 *   no papel), e antes vinha colado no nome como `"3. Arthur"`, o que obrigava a
 *   ler a linha inteira para achá-lo.
 * - **Resolvido não é cartão.** `entregue`/`ausente` perdem fundo e borda e ficam
 *   sobre o papel da tela: recuam de verdade, em vez de continuarem desenhando
 *   uma caixa com `opacity: 0.75` — que reduzia junto o contraste do texto e
 *   reprovava AA sem ninguém medir.
 * - **Barra de acento à esquerda** em vez de borda colorida em volta: a linha
 *   atual e a não-sincronizada se distinguem por um traço de 3dp que o olho pega
 *   na varredura vertical, sem mudar a massa da linha nem redesenhar contorno.
 */
import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { EstadoBadge } from "../../shared/components/EstadoBadge";
import type { TripStudentOut } from "../../shared/api/types";
import {
  TOQUE_MIN,
  type Paleta,
  espacamento,
  peso,
  raio,
  tipografia,
  useEstilos,
  useTema,
} from "../../shared/theme";
import { ehTerminal } from "../state/paradaAtual";
import { temAcoesForaDeOrdem } from "./MenuAcoesAluno";

interface Props {
  tripStudent: TripStudentOut;
  pendente: boolean;
  /** Destaca a linha do aluno que está no card do rodapé. */
  atual: boolean;
  reordenando: boolean;
  onAbrirAcoes: () => void;
  onMoverParaCima?: () => void;
  onMoverParaBaixo?: () => void;
}

export function AlunoRow({
  tripStudent,
  pendente,
  atual,
  reordenando,
  onAbrirAcoes,
  onMoverParaCima,
  onMoverParaBaixo,
}: Props): React.JSX.Element {
  const { cores } = useTema();
  const estilos = useEstilos(criarEstilos, cores);
  const resolvido = ehTerminal(tripStudent.estado);

  const acento = atual ? cores.marca : pendente ? cores.ambar : "transparent";

  return (
    <View style={[estilos.linha, resolvido ? estilos.linhaResolvida : estilos.linhaAtiva]}>
      <View style={[estilos.acento, { backgroundColor: acento }]} />

      <View style={estilos.conteudo}>
        <View style={estilos.topo}>
          <Text style={[estilos.ordem, resolvido && estilos.ordemResolvida]}>{tripStudent.ordem}</Text>

          <View style={estilos.info}>
            <Text style={[estilos.nome, resolvido && estilos.nomeResolvido]} numberOfLines={1}>
              {tripStudent.aluno_nome}
            </Text>
            {!resolvido && tripStudent.parada_endereco ? (
              <Text style={estilos.endereco} numberOfLines={1}>
                {tripStudent.parada_endereco}
              </Text>
            ) : null}
          </View>

          <EstadoBadge
            estado={tripStudent.estado}
            nomeAluno={tripStudent.aluno_nome}
            // Reordenando, o selo sai de cena: mudar o estado de um aluno no meio
            // de um rascunho de ordem misturaria duas operações.
            onPress={!reordenando && temAcoesForaDeOrdem(tripStudent.estado) ? onAbrirAcoes : undefined}
          />
        </View>

        {pendente ? <Text style={estilos.rotuloPendente}>na fila — ainda não sincronizado</Text> : null}

        {reordenando ? (
          tripStudent.estado === "aguardando" ? (
            <View style={estilos.setas}>
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={`Mover ${tripStudent.aluno_nome} para cima`}
                onPress={onMoverParaCima}
                android_ripple={{ color: cores.overlay }}
                style={({ pressed }) => [estilos.seta, pressed && estilos.setaPressionada]}
              >
                <Text style={estilos.setaTexto}>▲</Text>
              </Pressable>
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={`Mover ${tripStudent.aluno_nome} para baixo`}
                onPress={onMoverParaBaixo}
                android_ripple={{ color: cores.overlay }}
                style={({ pressed }) => [estilos.seta, pressed && estilos.setaPressionada]}
              >
                <Text style={estilos.setaTexto}>▼</Text>
              </Pressable>
            </View>
          ) : (
            <Text style={estilos.travadoReordenar}>já em andamento — não pode reordenar</Text>
          )
        ) : null}
      </View>
    </View>
  );
}

const criarEstilos = (cores: Paleta) =>
  StyleSheet.create({
    linha: {
      flexDirection: "row",
      borderRadius: raio.md,
      marginBottom: espacamento.sm,
      overflow: "hidden",
    },
    linhaAtiva: {
      backgroundColor: cores.cartao,
      borderWidth: 1,
      borderColor: cores.linha,
    },
    // Sem fundo nem borda: some no papel da tela em vez de continuar competindo
    // como cartão. É o que "recuar" quer dizer numa lista de consulta.
    linhaResolvida: {
      backgroundColor: "transparent",
    },
    acento: {
      width: 3,
    },
    conteudo: {
      flex: 1,
      paddingVertical: espacamento.md,
      paddingHorizontal: espacamento.md,
    },
    topo: {
      flexDirection: "row",
      alignItems: "center",
      gap: espacamento.md,
    },
    /** Largura fixa para os números alinharem entre as linhas — é o que permite
     * varrer a coluna com o olho em vez de ler cada linha. */
    ordem: {
      width: 22,
      textAlign: "center",
      fontSize: tipografia.subtitulo,
      fontWeight: peso.forte,
      color: cores.marca,
    },
    ordemResolvida: {
      color: cores.dica,
    },
    info: {
      flex: 1,
    },
    nome: {
      fontSize: tipografia.corpo,
      fontWeight: peso.forte,
      color: cores.tinta,
    },
    nomeResolvido: {
      color: cores.esmaecido,
    },
    endereco: {
      fontSize: tipografia.endereco,
      color: cores.esmaecido,
      marginTop: 2,
    },
    rotuloPendente: {
      fontSize: tipografia.legenda,
      color: cores.ambar,
      fontWeight: peso.forte,
      marginTop: espacamento.sm,
      marginLeft: 34,
    },
    setas: {
      flexDirection: "row",
      marginTop: espacamento.md,
      gap: espacamento.md,
    },
    seta: {
      minWidth: TOQUE_MIN,
      minHeight: TOQUE_MIN,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: cores.papel,
      borderWidth: 1,
      borderColor: cores.bordaAcao,
      borderRadius: raio.sm,
      overflow: "hidden",
    },
    setaPressionada: {
      opacity: 0.7,
    },
    setaTexto: {
      fontSize: tipografia.subtitulo,
      color: cores.tinta,
    },
    travadoReordenar: {
      marginTop: espacamento.md,
      marginLeft: 34,
      fontSize: tipografia.legenda,
      color: cores.dica,
    },
  });
