/**
 * Uma linha por aluno — CLAUDE.md §8: "uma ação por linha de aluno", alvo
 * de toque mínimo 56dp, estado sempre visível sem abrir nada.
 *
 * Interpretação de "uma ação por linha" (ambiguidade sinalizada antes da
 * implementação): o botão PRIMÁRIO é sempre único e muda com o estado
 * (Cheguei -> Checkin -> Checkout). "Ausente" é uma affordance SECUNDÁRIA,
 * deliberadamente menor e sem o peso visual de um segundo botão — não
 * compete com a ação primária pelo toque do motorista.
 */
import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { Botao56 } from "../../shared/components/Botao56";
import { EstadoBadge } from "../../shared/components/EstadoBadge";
import type { TripStudentOut } from "../../shared/api/types";
import { TOQUE_MIN, cores, espacamento, raio, tipografia } from "../../shared/theme";

interface Props {
  tripStudent: TripStudentOut;
  pendente: boolean;
  reordenando: boolean;
  onSolicitarCheguei: () => void;
  onCheckin: () => void;
  onCheckout: () => void;
  onAusente: () => void;
  onMoverParaCima?: () => void;
  onMoverParaBaixo?: () => void;
}

export function AlunoRow({
  tripStudent,
  pendente,
  reordenando,
  onSolicitarCheguei,
  onCheckin,
  onCheckout,
  onAusente,
  onMoverParaCima,
  onMoverParaBaixo,
}: Props): React.JSX.Element {
  const terminal = tripStudent.estado === "entregue" || tripStudent.estado === "ausente";
  const podeMarcarAusente = tripStudent.estado === "aguardando" || tripStudent.estado === "chegou";

  return (
    <View style={[estilos.linha, pendente && estilos.linhaPendente]}>
      <View style={estilos.topo}>
        <View style={estilos.info}>
          <Text style={estilos.nome} numberOfLines={1}>
            {tripStudent.ordem}. {tripStudent.aluno_nome}
          </Text>
          {tripStudent.parada_endereco ? (
            <Text style={estilos.endereco} numberOfLines={1}>
              {tripStudent.parada_endereco}
            </Text>
          ) : null}
        </View>
        <EstadoBadge estado={tripStudent.estado} />
      </View>

      {pendente ? <Text style={estilos.rotuloPendente}>não sincronizado — na fila</Text> : null}

      {reordenando ? (
        tripStudent.estado === "aguardando" ? (
          <View style={estilos.setas}>
            <Pressable
              accessibilityLabel={`Mover ${tripStudent.aluno_nome} para cima`}
              onPress={onMoverParaCima}
              style={estilos.seta}
            >
              <Text style={estilos.setaTexto}>▲</Text>
            </Pressable>
            <Pressable
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
      ) : (
        <View style={estilos.acoes}>
          {tripStudent.estado === "aguardando" && (
            <Botao56 titulo="Cheguei" onPress={onSolicitarCheguei} estilo={estilos.botaoPrimario} />
          )}
          {tripStudent.estado === "chegou" && (
            <Botao56 titulo="Checkin" onPress={onCheckin} estilo={estilos.botaoPrimario} />
          )}
          {tripStudent.estado === "a_bordo" && (
            <Botao56 titulo="Checkout" onPress={onCheckout} estilo={estilos.botaoPrimario} />
          )}
          {terminal && <View style={estilos.botaoPrimario} />}

          {podeMarcarAusente && (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={`Marcar ${tripStudent.aluno_nome} como ausente`}
              onPress={onAusente}
              style={estilos.ausenteBotao}
              hitSlop={8}
            >
              <Text style={estilos.ausenteTexto}>Ausente</Text>
            </Pressable>
          )}
        </View>
      )}
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
  linhaPendente: {
    borderStyle: "dashed",
    borderColor: cores.ambar,
  },
  topo: {
    flexDirection: "row",
    alignItems: "flex-start",
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
  endereco: {
    fontSize: 12,
    color: cores.esmaecido,
    marginTop: 2,
  },
  rotuloPendente: {
    fontSize: 11,
    color: cores.ambar,
    fontWeight: "600",
    marginTop: espacamento.xs,
  },
  acoes: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: espacamento.md,
    gap: espacamento.md,
  },
  botaoPrimario: {
    flex: 1,
  },
  ausenteBotao: {
    minHeight: TOQUE_MIN,
    justifyContent: "center",
    paddingHorizontal: espacamento.sm,
  },
  ausenteTexto: {
    fontSize: 13,
    fontWeight: "600",
    color: cores.esmaecido,
    textDecorationLine: "underline",
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
    fontSize: 12,
    color: cores.dica,
    fontStyle: "italic",
  },
});
