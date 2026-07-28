/**
 * Tela 4 — Finalizar viagem: varredura final bloqueante (CLAUDE.md §7.1,
 * regra inviolável). Não deixa finalizar com aluno em estado não terminal;
 * alerta duro se alguém ainda estiver `a_bordo` (aluno esquecido a bordo é
 * o pior caso).
 *
 * `POST /finalizar` é online-only e é sempre a autoridade final — mesmo que
 * a lista local pareça limpa, um 409 aqui significa que algo mudou entre a
 * última sincronização e agora, e a tela ressincroniza em vez de insistir.
 */
import React, { useState } from "react";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { FlatList, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { ApiError, NetworkError } from "../../shared/api/client";
import { endpoints } from "../../shared/api/endpoints";
import { Botao56 } from "../../shared/components/Botao56";
import { DialogoConfirmacao } from "../../shared/components/DialogoConfirmacao";
import { EstadoBadge } from "../../shared/components/EstadoBadge";
import { LinkToque } from "../../shared/components/LinkToque";
import { PillSync } from "../../shared/components/PillSync";
import { hapticoAcao, hapticoErro } from "../../shared/feedback/haptico";
import { cores, espacamento, raio, tipografia } from "../../shared/theme";
import type { RootStackParamList } from "../../navigation/RootNavigator";
import { useViagemStore } from "../state/ViagemStore";

type Props = NativeStackScreenProps<RootStackParamList, "FinalizarViagem">;

export function FinalizarViagemScreen({ route, navigation }: Props): React.JSX.Element {
  const { viagemId } = route.params;
  const store = useViagemStore(viagemId);
  const insets = useSafeAreaInsets();
  const [finalizando, setFinalizando] = useState(false);
  const [confirmando, setConfirmando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const pendentes = store.todosNaoTerminais;
  const algumABordo = pendentes.some((ts) => ts.estado === "a_bordo");
  const haPendenteNaFila = Object.keys(store.pendentesPorTripStudent).length > 0;
  const bloqueado = store.carregando || pendentes.length > 0 || haPendenteNaFila;

  const rotuloBotao = store.carregando
    ? "Carregando..."
    : pendentes.length > 0
      ? `Faltam ${pendentes.length} aluno${pendentes.length === 1 ? "" : "s"}`
      : haPendenteNaFila
        ? "Aguardando sincronizar..."
        : "Veículo vazio — finalizar";

  const entregues = store.tripStudents.filter((ts) => ts.estado === "entregue").length;
  const ausentes = store.tripStudents.filter((ts) => ts.estado === "ausente").length;

  async function finalizar() {
    setConfirmando(false);
    setFinalizando(true);
    setErro(null);
    try {
      await endpoints.finalizarViagem(viagemId);
      hapticoAcao();
      navigation.popToTop();
    } catch (e) {
      hapticoErro();
      if (e instanceof ApiError && e.status === 409) {
        setErro("Algo mudou desde a última checagem — atualizando a lista.");
        await store.recarregar();
      } else if (e instanceof NetworkError) {
        setErro("Sem conexão — não é possível finalizar agora. Tente de novo.");
      } else if (e instanceof ApiError) {
        setErro(e.detail);
      } else {
        setErro("Não foi possível finalizar a viagem.");
      }
    } finally {
      setFinalizando(false);
    }
  }

  return (
    <View style={estilos.tela}>
      <View
        style={[
          estilos.cabecalho,
          { paddingTop: espacamento.lg + insets.top },
          algumABordo ? estilos.cabecalhoAlerta : estilos.cabecalhoAviso,
        ]}
      >
        <Text style={estilos.tituloCabecalho}>{algumABordo ? "Aluno a bordo!" : "Verificação obrigatória"}</Text>
        <Text style={estilos.subtituloCabecalho}>
          {algumABordo
            ? "Confira o veículo — há aluno sem checkout."
            : "Todo aluno precisa estar entregue ou ausente antes de finalizar."}
        </Text>
      </View>

      <PillSync />

      {erro ? <Text style={estilos.erro}>{erro}</Text> : null}
      {haPendenteNaFila ? (
        <Text style={estilos.avisoFila}>Há eventos ainda não sincronizados — aguarde a fila esvaziar.</Text>
      ) : null}

      <FlatList
        data={pendentes}
        keyExtractor={(ts) => ts.id}
        contentContainerStyle={estilos.lista}
        ListEmptyComponent={
          !store.carregando ? <Text style={estilos.tudoOk}>Todos os alunos concluídos. Pode finalizar.</Text> : null
        }
        renderItem={({ item }) => (
          <View style={estilos.linha}>
            <View style={estilos.linhaInfo}>
              <Text style={estilos.nome} numberOfLines={1}>
                {item.ordem}. {item.aluno_nome}
              </Text>
              <Text style={estilos.dica}>volte e resolva na tela da viagem</Text>
            </View>
            <EstadoBadge estado={item.estado} />
          </View>
        )}
      />

      <View style={[estilos.rodape, { paddingBottom: espacamento.lg + insets.bottom }]}>
        <Botao56
          titulo={rotuloBotao}
          variante={bloqueado ? "secundario" : "primario"}
          tamanho="grande"
          desabilitado={bloqueado}
          carregando={finalizando}
          onPress={() => setConfirmando(true)}
        />
        <LinkToque
          titulo="Voltar para a viagem"
          cor={cores.esmaecido}
          onPress={() => navigation.goBack()}
        />
      </View>

      {/* O diálogo entra DEPOIS do gate da varredura (§7.1), nunca no lugar
          dele: o botão só habilita com todos os alunos em estado terminal, e a
          autoridade final continua sendo o 409 do servidor. Aqui a confirmação
          cobre outra coisa — finalizar encerra a viagem e não há reabertura. */}
      <DialogoConfirmacao
        visivel={confirmando}
        titulo="Finalizar viagem"
        subtitulo={`${entregues} entregue${entregues === 1 ? "" : "s"}, ${ausentes} ausente${ausentes === 1 ? "" : "s"}. Não dá para reabrir.`}
        rotuloConfirmar="Finalizar"
        varianteConfirmar="destrutivo"
        onConfirmar={() => void finalizar()}
        onCancelar={() => setConfirmando(false)}
      />
    </View>
  );
}

const estilos = StyleSheet.create({
  tela: {
    flex: 1,
    backgroundColor: cores.papel,
  },
  cabecalho: {
    paddingHorizontal: espacamento.lg,
    paddingBottom: espacamento.lg,
  },
  cabecalhoAviso: {
    backgroundColor: cores.ambarSuave,
  },
  cabecalhoAlerta: {
    backgroundColor: cores.perigoSuave,
  },
  tituloCabecalho: {
    fontSize: 16,
    fontWeight: "700",
    color: cores.tinta,
  },
  subtituloCabecalho: {
    fontSize: 12.5,
    color: cores.esmaecido,
    marginTop: 2,
  },
  erro: {
    color: cores.perigo,
    fontSize: 12.5,
    fontWeight: "600",
    paddingHorizontal: espacamento.lg,
    paddingTop: espacamento.sm,
  },
  avisoFila: {
    color: cores.ambar,
    fontSize: 12.5,
    fontWeight: "600",
    paddingHorizontal: espacamento.lg,
    paddingTop: espacamento.sm,
  },
  lista: {
    padding: espacamento.lg,
    flexGrow: 1,
  },
  tudoOk: {
    textAlign: "center",
    color: cores.marca,
    fontWeight: "600",
    marginTop: espacamento.xl,
  },
  linha: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: cores.cartao,
    borderRadius: raio.md,
    borderWidth: 1,
    borderColor: cores.linha,
    padding: espacamento.md,
    marginBottom: espacamento.sm,
  },
  linhaInfo: {
    flex: 1,
    marginRight: espacamento.sm,
  },
  nome: {
    fontSize: tipografia.corpo,
    fontWeight: "700",
    color: cores.tinta,
  },
  dica: {
    fontSize: 11.5,
    color: cores.dica,
    marginTop: 2,
  },
  rodape: {
    padding: espacamento.lg,
    gap: espacamento.sm,
  },
});
