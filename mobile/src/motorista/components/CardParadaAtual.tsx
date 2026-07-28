/**
 * Card da parada atual — a única ação primária da tela (Bloco B7).
 *
 * Antes do B7 a `ViagemScreen` era uma lista uniforme de N alunos, todos com o
 * mesmo peso visual e um botão cada. O motorista tinha que LER a tela e ACHAR
 * qual linha era a dele — parado em fila dupla, com a van ligada. Numa rota de
 * doze alunos, depois de oito entregues o alvo já estava fora da tela.
 *
 * Aqui a ação vem até ele: fica no rodapé (zona do polegar, não no topo), ocupa
 * a largura toda, tem 72dp de altura e nunca sai da tela. A lista acima virou
 * consulta. Efeito colateral bem-vindo: como o alvo não rola, não é preciso
 * `scrollToIndex` — um mecanismo a menos para falhar.
 *
 * O badge fica tocável aqui pelo mesmo motivo que fica na lista: é o canal das
 * ações fora de ordem (§4 — desfazer chegada, marcar ausente). Ter o badge no
 * card evita que o motorista precise caçar a linha do aluno pra corrigir a
 * parada em que ele está parado agora.
 */
import React, { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Botao56 } from "../../shared/components/Botao56";
import { EstadoBadge } from "../../shared/components/EstadoBadge";
import type { TripStudentOut } from "../../shared/api/types";
import { cores, espacamento, raio, tipografia } from "../../shared/theme";
import { formatarEspera, type FaseViagem } from "../state/paradaAtual";
import { temAcoesForaDeOrdem } from "./MenuAcoesAluno";

const ROTULO_ACAO: Record<string, string> = {
  aguardando: "Cheguei",
  chegou: "Checkin",
  a_bordo: "Checkout",
};

interface Props {
  alvo: TripStudentOut;
  fase: FaseViagem;
  pendente: boolean;
  onAcaoPrimaria: () => void;
  onAbrirAcoes: () => void;
}

export function CardParadaAtual({
  alvo,
  fase,
  pendente,
  onAcaoPrimaria,
  onAbrirAcoes,
}: Props): React.JSX.Element {
  const insets = useSafeAreaInsets();
  const [agoraMs, setAgoraMs] = useState(() => Date.now());

  // Cronômetro só corre enquanto o motorista está de fato esperando na porta.
  useEffect(() => {
    if (alvo.estado !== "chegou" || !alvo.chegou_em) return undefined;
    const intervalo = setInterval(() => setAgoraMs(Date.now()), 1000);
    return () => clearInterval(intervalo);
  }, [alvo.estado, alvo.chegou_em]);

  // No desembarque o endereço da parada é o ponto de EMBARQUE (snapshot da
  // origem — ver docstring de models/trip_student.py). Mostrá-lo enquanto a van
  // descarrega na escola apontaria o motorista para o lugar errado.
  const legenda =
    fase === "desembarque"
      ? "Desembarque no destino"
      : alvo.estado === "chegou" && alvo.chegou_em
        ? formatarEspera(alvo.chegou_em, agoraMs)
        : alvo.parada_endereco;

  return (
    <View style={[estilos.base, { paddingBottom: espacamento.lg + insets.bottom }]}>
      <View style={estilos.topo}>
        <Text style={estilos.nome} numberOfLines={1}>
          {alvo.ordem}. {alvo.aluno_nome}
        </Text>
        <EstadoBadge
          estado={alvo.estado}
          nomeAluno={alvo.aluno_nome}
          onPress={temAcoesForaDeOrdem(alvo.estado) ? onAbrirAcoes : undefined}
        />
      </View>

      {legenda ? (
        <Text style={estilos.legenda} numberOfLines={1}>
          {legenda}
        </Text>
      ) : null}

      {pendente ? <Text style={estilos.pendente}>não sincronizado — na fila</Text> : null}

      <Botao56
        titulo={ROTULO_ACAO[alvo.estado] ?? "Aguarde"}
        tamanho="grande"
        onPress={onAcaoPrimaria}
        estilo={estilos.acao}
        testID="acao-primaria"
      />
    </View>
  );
}

const estilos = StyleSheet.create({
  base: {
    backgroundColor: cores.cartao,
    borderTopWidth: 1,
    borderTopColor: cores.linha2,
    borderTopLeftRadius: raio.lg,
    borderTopRightRadius: raio.lg,
    paddingHorizontal: espacamento.lg,
    paddingTop: espacamento.lg,
    gap: espacamento.xs,
  },
  topo: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: espacamento.sm,
  },
  nome: {
    flex: 1,
    fontSize: tipografia.destaque,
    fontWeight: "700",
    color: cores.tinta,
  },
  legenda: {
    fontSize: tipografia.endereco,
    color: cores.esmaecido,
  },
  pendente: {
    fontSize: tipografia.legenda,
    color: cores.ambar,
    fontWeight: "600",
  },
  acao: {
    marginTop: espacamento.md,
  },
});
