/**
 * Uma linha por aluno — CLAUDE.md §8: estado sempre visível sem abrir nada.
 *
 * Bloco B7 — a linha PERDEU os botões de ação. Antes ela carregava o botão
 * primário (Cheguei/Checkin/Checkout) e mais um "Ausente" a 12dp dele: dois
 * alvos competindo pelo polegar, numa van em movimento, sendo que um deles é
 * irreversível. O §8 pede "uma ação por linha" e a linha tinha duas.
 *
 * Agora a ação primária vive só no card do rodapé, e o que sobra aqui é
 * consulta + o badge, que abre as ações fora de ordem (ver `MenuAcoesAluno`).
 *
 * Dois modos, porque a lista precisa caber na tela: alunos já resolvidos viram
 * uma linha compacta (antes cada um gastava ~110dp de altura útil, incluindo um
 * `View` vazio só para preservar o alinhamento dos botões).
 */
import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { EstadoBadge } from "../../shared/components/EstadoBadge";
import type { TripStudentOut } from "../../shared/api/types";
import { TOQUE_MIN, cores, espacamento, raio, tipografia } from "../../shared/theme";
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
  const compacto = ehTerminal(tripStudent.estado);

  return (
    <View
      style={[
        estilos.linha,
        compacto && estilos.linhaCompacta,
        atual && estilos.linhaAtual,
        pendente && estilos.linhaPendente,
      ]}
    >
      <View style={estilos.topo}>
        <View style={estilos.info}>
          <Text style={[estilos.nome, compacto && estilos.nomeCompacto]} numberOfLines={1}>
            {tripStudent.ordem}. {tripStudent.aluno_nome}
          </Text>
          {!compacto && tripStudent.parada_endereco ? (
            <Text style={estilos.endereco} numberOfLines={1}>
              {tripStudent.parada_endereco}
            </Text>
          ) : null}
        </View>
        <EstadoBadge
          estado={tripStudent.estado}
          nomeAluno={tripStudent.aluno_nome}
          // Reordenando, o badge sai de cena: mudar o estado de um aluno no meio
          // de um rascunho de ordem misturaria duas operações.
          onPress={!reordenando && temAcoesForaDeOrdem(tripStudent.estado) ? onAbrirAcoes : undefined}
        />
      </View>

      {pendente ? <Text style={estilos.rotuloPendente}>não sincronizado — na fila</Text> : null}

      {reordenando ? (
        tripStudent.estado === "aguardando" ? (
          <View style={estilos.setas}>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={`Mover ${tripStudent.aluno_nome} para cima`}
              onPress={onMoverParaCima}
              style={estilos.seta}
            >
              <Text style={estilos.setaTexto}>▲</Text>
            </Pressable>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={`Mover ${tripStudent.aluno_nome} para baixo`}
              onPress={onMoverParaBaixo}
              style={estilos.seta}
            >
              <Text style={estilos.setaTexto}>▼</Text>
            </Pressable>
          </View>
        ) : (
          <Text style={estilos.travadoReordenar}>já em andamento — não pode reordenar</Text>
        )
      ) : null}
    </View>
  );
}

const estilos = StyleSheet.create({
  linha: {
    backgroundColor: cores.cartao,
    borderRadius: raio.md,
    borderWidth: 1,
    borderColor: cores.linha,
    padding: espacamento.md,
    marginBottom: espacamento.sm,
  },
  linhaCompacta: {
    paddingVertical: espacamento.sm,
    opacity: 0.75,
  },
  linhaAtual: {
    borderColor: cores.marca,
    borderWidth: 2,
  },
  linhaPendente: {
    borderStyle: "dashed",
    borderColor: cores.ambar,
  },
  topo: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: espacamento.sm,
  },
  info: {
    flex: 1,
  },
  nome: {
    fontSize: tipografia.corpo,
    fontWeight: "700",
    color: cores.tinta,
  },
  nomeCompacto: {
    fontWeight: "600",
  },
  endereco: {
    fontSize: tipografia.endereco,
    color: cores.esmaecido,
    marginTop: 2,
  },
  rotuloPendente: {
    fontSize: tipografia.legenda,
    color: cores.ambar,
    fontWeight: "600",
    marginTop: espacamento.xs,
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
    borderRadius: raio.sm,
  },
  setaTexto: {
    fontSize: 18,
    color: cores.tinta,
  },
  travadoReordenar: {
    marginTop: espacamento.md,
    fontSize: tipografia.legenda,
    color: cores.dica,
    fontStyle: "italic",
  },
});
