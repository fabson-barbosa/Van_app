/**
 * Tela 4 — Finalizar viagem: varredura final bloqueante (CLAUDE.md §7.1, regra
 * inviolável). Não deixa finalizar com aluno em estado não terminal; alerta duro
 * se alguém ainda estiver `a_bordo` (aluno esquecido a bordo é o pior caso).
 *
 * `POST /finalizar` é online-only e é sempre a autoridade final — mesmo que a
 * lista local pareça limpa, um 409 aqui significa que algo mudou entre a última
 * sincronização e agora, e a tela ressincroniza em vez de insistir.
 *
 * Bloco B8 — o alerta duro passou a PARECER um alerta duro:
 *
 * - O cabeçalho de "Aluno a bordo!" era uma faixa cor-de-rosa clara com título de
 *   16sp — mesmo peso do cabeçalho de rotina. Agora o caso grave usa preenchimento
 *   vermelho sólido e ocupa a tela; é a única regra inviolável que depende de o
 *   motorista PARAR e conferir o veículo.
 * - O placar de entregues/ausentes/a bordo virou três números grandes no lugar de
 *   uma frase dentro do diálogo. É o que ele confere antes de fechar o turno.
 * - A lista de pendentes ganhou o número da parada, alinhado como na tela da
 *   viagem, para ele achar quem falta na mesma varredura visual.
 */
import React, { useMemo, useState } from "react";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { FlatList, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { ApiError, NetworkError } from "../../shared/api/client";
import { endpoints } from "../../shared/api/endpoints";
import { Banner } from "../../shared/components/Banner";
import { Botao56 } from "../../shared/components/Botao56";
import { DialogoConfirmacao } from "../../shared/components/DialogoConfirmacao";
import { EstadoBadge } from "../../shared/components/EstadoBadge";
import { LinkToque } from "../../shared/components/LinkToque";
import { PillSync } from "../../shared/components/PillSync";
import { feedbackConcluido, feedbackErro } from "../../shared/feedback";
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
import type { RootStackParamList } from "../../navigation/RootNavigator";
import { useViagemStore } from "../state/ViagemStore";

type Props = NativeStackScreenProps<RootStackParamList, "FinalizarViagem">;

export function FinalizarViagemScreen({ route, navigation }: Props): React.JSX.Element {
  const { viagemId } = route.params;
  const { cores } = useTema();
  const estilos = useEstilos(criarEstilos, cores);
  const store = useViagemStore(viagemId);
  const insets = useSafeAreaInsets();
  const [finalizando, setFinalizando] = useState(false);
  const [confirmando, setConfirmando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const pendentes = store.todosNaoTerminais;
  const algumABordo = pendentes.some((ts) => ts.estado === "a_bordo");
  const haPendenteNaFila = Object.keys(store.pendentesPorTripStudent).length > 0;
  const bloqueado = store.carregando || pendentes.length > 0 || haPendenteNaFila;

  const placar = useMemo(
    () => ({
      entregues: store.tripStudents.filter((ts) => ts.estado === "entregue").length,
      ausentes: store.tripStudents.filter((ts) => ts.estado === "ausente").length,
      aBordo: store.tripStudents.filter((ts) => ts.estado === "a_bordo").length,
    }),
    [store.tripStudents]
  );

  const rotuloBotao = store.carregando
    ? "Carregando..."
    : pendentes.length > 0
      ? `Faltam ${pendentes.length} aluno${pendentes.length === 1 ? "" : "s"}`
      : haPendenteNaFila
        ? "Aguardando sincronizar..."
        : "Veículo vazio — finalizar";

  async function finalizar() {
    setConfirmando(false);
    setFinalizando(true);
    setErro(null);
    try {
      await endpoints.finalizarViagem(viagemId);
      feedbackConcluido();
      navigation.popToTop();
    } catch (e) {
      feedbackErro();
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
          algumABordo ? estilos.cabecalhoAlerta : estilos.cabecalhoNormal,
        ]}
      >
        <Text style={[estilos.rotuloCabecalho, algumABordo && estilos.textoAlerta]}>
          {algumABordo ? "ATENÇÃO" : "VERIFICAÇÃO OBRIGATÓRIA"}
        </Text>
        <Text style={[estilos.tituloCabecalho, algumABordo && estilos.textoAlerta]}>
          {algumABordo
            ? `${placar.aBordo} aluno${placar.aBordo === 1 ? "" : "s"} ainda a bordo`
            : "Confira o veículo"}
        </Text>
        <Text style={[estilos.subtituloCabecalho, algumABordo && estilos.textoAlertaSuave]}>
          {algumABordo
            ? "Percorra a van antes de finalizar. Ninguém pode ficar dentro do veículo."
            : "Todo aluno precisa estar entregue ou ausente antes de finalizar."}
        </Text>
      </View>

      <View style={estilos.placar}>
        <View style={estilos.placarItem}>
          <Text style={[estilos.placarNumero, { color: cores.marca }]}>{placar.entregues}</Text>
          <Text style={estilos.placarRotulo}>ENTREGUES</Text>
        </View>
        <View style={estilos.placarDivisor} />
        <View style={estilos.placarItem}>
          <Text style={[estilos.placarNumero, { color: cores.ambar }]}>{placar.ausentes}</Text>
          <Text style={estilos.placarRotulo}>AUSENTES</Text>
        </View>
        <View style={estilos.placarDivisor} />
        <View style={estilos.placarItem}>
          <Text style={[estilos.placarNumero, { color: placar.aBordo > 0 ? cores.perigo : cores.dica }]}>
            {placar.aBordo}
          </Text>
          <Text style={estilos.placarRotulo}>A BORDO</Text>
        </View>
      </View>

      <PillSync />

      {erro ? <Banner tom="erro" mensagem={erro} /> : null}
      {haPendenteNaFila ? (
        <Banner tom="aviso" mensagem="Há eventos ainda não sincronizados — aguarde a fila esvaziar." />
      ) : null}

      <FlatList
        data={pendentes}
        keyExtractor={(ts) => ts.id}
        contentContainerStyle={estilos.lista}
        ListHeaderComponent={
          pendentes.length > 0 ? <Text style={estilos.secaoLista}>FALTA RESOLVER</Text> : null
        }
        ListEmptyComponent={
          !store.carregando ? (
            <View style={estilos.tudoOk}>
              <Text style={estilos.tudoOkTitulo}>Todos os alunos resolvidos</Text>
              <Text style={estilos.tudoOkDica}>Pode finalizar a viagem.</Text>
            </View>
          ) : null
        }
        renderItem={({ item }) => (
          <View style={estilos.linha}>
            <Text style={estilos.ordem}>{item.ordem}</Text>
            <View style={estilos.linhaInfo}>
              <Text style={estilos.nome} numberOfLines={1}>
                {item.aluno_nome}
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
        <LinkToque titulo="Voltar para a viagem" cor={cores.esmaecido} onPress={() => navigation.goBack()} />
      </View>

      {/* O diálogo entra DEPOIS do gate da varredura (§7.1), nunca no lugar dele:
          o botão só habilita com todos os alunos em estado terminal, e a
          autoridade final continua sendo o 409 do servidor. Aqui a confirmação
          cobre outra coisa — finalizar encerra a viagem e não há reabertura. */}
      <DialogoConfirmacao
        visivel={confirmando}
        titulo="Finalizar viagem"
        subtitulo={`${placar.entregues} entregue${placar.entregues === 1 ? "" : "s"}, ${placar.ausentes} ausente${placar.ausentes === 1 ? "" : "s"}. Não dá para reabrir.`}
        rotuloConfirmar="Finalizar"
        varianteConfirmar="destrutivo"
        onConfirmar={() => void finalizar()}
        onCancelar={() => setConfirmando(false)}
      />
    </View>
  );
}

const criarEstilos = (cores: Paleta) =>
  StyleSheet.create({
    tela: {
      flex: 1,
      backgroundColor: cores.papel,
    },
    cabecalho: {
      paddingHorizontal: espacamento.lg,
      paddingBottom: espacamento.lg,
    },
    cabecalhoNormal: {
      backgroundColor: cores.cartao,
      borderBottomWidth: 1,
      borderBottomColor: cores.linha,
    },
    // Preenchimento sólido: é a única regra inviolável que exige o motorista
    // parar e percorrer o veículo (§7.1). Faixa clara não carrega esse peso.
    cabecalhoAlerta: {
      backgroundColor: cores.perigoForte,
    },
    rotuloCabecalho: {
      fontSize: tipografia.legenda,
      fontWeight: peso.forte,
      letterSpacing: ESPACO_LETRA_SELO,
      color: cores.dica,
    },
    tituloCabecalho: {
      fontSize: tipografia.destaque,
      fontWeight: peso.forte,
      color: cores.tinta,
      marginTop: espacamento.xs,
    },
    subtituloCabecalho: {
      fontSize: tipografia.endereco,
      color: cores.esmaecido,
      marginTop: espacamento.xs,
      lineHeight: tipografia.endereco * 1.4,
    },
    textoAlerta: {
      color: cores.sobrePerigo,
    },
    textoAlertaSuave: {
      color: cores.sobrePerigo,
      opacity: 0.9,
    },
    placar: {
      flexDirection: "row",
      alignItems: "center",
      backgroundColor: cores.cartao,
      borderBottomWidth: 1,
      borderBottomColor: cores.linha,
      paddingVertical: espacamento.md,
    },
    placarItem: {
      flex: 1,
      alignItems: "center",
    },
    placarDivisor: {
      width: 1,
      alignSelf: "stretch",
      backgroundColor: cores.linha,
    },
    placarNumero: {
      fontSize: tipografia.numero,
      fontWeight: peso.forte,
    },
    placarRotulo: {
      fontSize: tipografia.legenda,
      fontWeight: peso.forte,
      letterSpacing: ESPACO_LETRA_SELO,
      color: cores.dica,
      marginTop: 2,
    },
    lista: {
      padding: espacamento.lg,
      flexGrow: 1,
    },
    secaoLista: {
      fontSize: tipografia.legenda,
      fontWeight: peso.forte,
      letterSpacing: ESPACO_LETRA_SELO,
      color: cores.dica,
      marginBottom: espacamento.sm,
    },
    tudoOk: {
      alignItems: "center",
      marginTop: espacamento.xxl,
    },
    tudoOkTitulo: {
      fontSize: tipografia.subtitulo,
      fontWeight: peso.forte,
      color: cores.marca,
    },
    tudoOkDica: {
      fontSize: tipografia.endereco,
      color: cores.esmaecido,
      marginTop: espacamento.xs,
    },
    linha: {
      flexDirection: "row",
      alignItems: "center",
      gap: espacamento.md,
      backgroundColor: cores.cartao,
      borderRadius: raio.md,
      borderWidth: 1,
      borderColor: cores.linha,
      padding: espacamento.md,
      marginBottom: espacamento.sm,
    },
    ordem: {
      width: 22,
      textAlign: "center",
      fontSize: tipografia.subtitulo,
      fontWeight: peso.forte,
      color: cores.perigo,
    },
    linhaInfo: {
      flex: 1,
    },
    nome: {
      fontSize: tipografia.corpo,
      fontWeight: peso.forte,
      color: cores.tinta,
    },
    dica: {
      fontSize: tipografia.legenda,
      color: cores.dica,
      marginTop: 2,
    },
    rodape: {
      padding: espacamento.lg,
      gap: espacamento.sm,
      backgroundColor: cores.cartao,
      borderTopWidth: 1,
      borderTopColor: cores.linha2,
      borderTopLeftRadius: raio.lg,
      borderTopRightRadius: raio.lg,
    },
  });
