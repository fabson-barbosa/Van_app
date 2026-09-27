/**
 * Tela 2 — Rota do dia: viagens da jornada do motorista, iniciar viagem.
 *
 * Bloco B8 — era uma lista de cartões com três linhas de texto do mesmo peso
 * (`rota_nome` em 16sp, um `meta` de 12,5sp concatenando turno · nº de alunos ·
 * status, e um botão). Três mudanças:
 *
 * - **O status virou selo, não texto concatenado.** "Em andamento" é o dado que
 *   decide se o motorista está retomando um turno ou começando outro, e estava
 *   no fim de uma frase com separadores "·", no menor tamanho da tela.
 * - **A viagem em andamento sobe e é destacada.** Se existe uma aberta, é ela que
 *   ele quer — e antes vinha na ordem que o backend devolvesse, com o mesmo peso
 *   visual de uma finalizada.
 * - **"Sair" saiu do cabeçalho** para as Preferências (nova tela). Estava a
 *   poucos dp do botão que inicia o turno, e derrubar a sessão com a fila offline
 *   dentro dela é a última coisa que se quer por engano.
 */
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useFocusEffect } from "@react-navigation/native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { FlatList, Pressable, RefreshControl, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Banner } from "../../shared/components/Banner";
import { Botao56 } from "../../shared/components/Botao56";
import { ApiError, NetworkError } from "../../shared/api/client";
import { endpoints } from "../../shared/api/endpoints";
import type { ViagemOut } from "../../shared/api/types";
import { useAuth } from "../../shared/auth/AuthContext";
import { feedbackErro } from "../../shared/feedback";
import {
  ESPACO_LETRA_SELO,
  TOQUE_MIN,
  type Paleta,
  espacamento,
  peso,
  raio,
  tipografia,
  useEstilos,
  useTema,
} from "../../shared/theme";
import type { RootStackParamList } from "../../navigation/RootNavigator";

type Props = NativeStackScreenProps<RootStackParamList, "RotaDoDia">;

const ROTULO_STATUS: Record<ViagemOut["status"], string> = {
  planejada: "Planejada",
  em_andamento: "Em andamento",
  finalizada: "Finalizada",
};

/** Em andamento primeiro (é o que ele quer retomar), depois planejada, e as
 * finalizadas no fim — elas são só histórico do dia. */
const PESO_STATUS: Record<ViagemOut["status"], number> = {
  em_andamento: 0,
  planejada: 1,
  finalizada: 2,
};

export function RotaDoDiaScreen({ navigation }: Props): React.JSX.Element {
  const { cores } = useTema();
  const estilos = useEstilos(criarEstilos, cores);
  const { token } = useAuth();
  const insets = useSafeAreaInsets();
  const [viagens, setViagens] = useState<ViagemOut[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [iniciandoId, setIniciandoId] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    setErro(null);
    try {
      const dados = await endpoints.listarViagens();
      setViagens(dados);
    } catch (e) {
      setErro(
        e instanceof NetworkError
          ? "Sem conexão — verifique o sinal e tente de novo."
          : e instanceof ApiError
            ? e.detail
            : "Não foi possível carregar as viagens de hoje."
      );
    } finally {
      setCarregando(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      void carregar();
    }, [carregar])
  );

  // `useFocusEffect` só reage a eventos de navegação — o modal de reautenticação
  // (RootNavigator) fica POR CIMA desta tela sem tirar o foco dela, então logar
  // de novo não retriggava esse efeito e a lista ficava presa no erro da primeira
  // busca (feita com o token vencido). Achado testando em aparelho físico real.
  useEffect(() => {
    if (token) void carregar();
  }, [token, carregar]);

  const ordenadas = useMemo(
    () => [...viagens].sort((a, b) => PESO_STATUS[a.status] - PESO_STATUS[b.status]),
    [viagens]
  );

  const abrirViagem = async (viagem: ViagemOut) => {
    if (viagem.status === "planejada") {
      setIniciandoId(viagem.id);
      try {
        await endpoints.iniciarViagem(viagem.id);
      } catch (e) {
        setIniciandoId(null);
        feedbackErro();
        setErro(
          e instanceof NetworkError
            ? "Sem conexão — não é possível iniciar a viagem agora. Tente de novo."
            : e instanceof ApiError
              ? e.detail
              : "Não foi possível iniciar a viagem."
        );
        return;
      }
      setIniciandoId(null);
    }
    navigation.navigate("Viagem", { viagemId: viagem.id });
  };

  return (
    <View style={estilos.tela}>
      <View style={[estilos.cabecalho, { paddingTop: espacamento.lg + insets.top }]}>
        <View style={estilos.cabecalhoInfo}>
          <Text style={estilos.saudacao}>Rota do dia</Text>
          <Text style={estilos.contagem}>
            {carregando
              ? "Carregando..."
              : `${viagens.length} viagem${viagens.length === 1 ? "" : "s"} hoje`}
          </Text>
        </View>

        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Preferências"
          onPress={() => navigation.navigate("Preferencias")}
          android_ripple={{ color: cores.overlay, borderless: true }}
          hitSlop={12}
          style={({ pressed }) => [estilos.botaoPrefs, pressed && estilos.botaoPrefsPressionado]}
        >
          {/* Três barras horizontais: ícone de ajustes sem depender de biblioteca
              de ícones, que o projeto não tem. */}
          <View style={[estilos.barraIcone, estilos.barraLonga]} />
          <View style={[estilos.barraIcone, estilos.barraMedia]} />
          <View style={[estilos.barraIcone, estilos.barraCurta]} />
        </Pressable>
      </View>

      {erro ? (
        <Banner tom="erro" mensagem={erro} acao={{ titulo: "Tentar de novo", onPress: () => void carregar() }} />
      ) : null}

      <FlatList
        data={ordenadas}
        keyExtractor={(v) => v.id}
        contentContainerStyle={[estilos.lista, { paddingBottom: espacamento.lg + insets.bottom }]}
        refreshControl={
          <RefreshControl
            refreshing={carregando}
            onRefresh={carregar}
            tintColor={cores.marca}
            colors={[cores.marca]}
          />
        }
        ListEmptyComponent={
          !carregando ? <Text style={estilos.vazio}>Nenhuma viagem para hoje.</Text> : null
        }
        renderItem={({ item }) => {
          const emAndamento = item.status === "em_andamento";
          const finalizada = item.status === "finalizada";
          return (
            <View style={[estilos.cartao, emAndamento && estilos.cartaoAtivo]}>
              <View style={estilos.cartaoTopo}>
                <Text style={[estilos.nomeRota, finalizada && estilos.nomeRotaFinalizada]} numberOfLines={2}>
                  {item.rota_nome}
                </Text>
                <View
                  style={[
                    estilos.selo,
                    emAndamento ? estilos.seloAtivo : finalizada ? estilos.seloFeito : estilos.seloPlanejado,
                  ]}
                >
                  <Text
                    style={[
                      estilos.seloTexto,
                      emAndamento
                        ? estilos.seloTextoAtivo
                        : finalizada
                          ? estilos.seloTextoFeito
                          : estilos.seloTextoPlanejado,
                    ]}
                  >
                    {ROTULO_STATUS[item.status].toUpperCase()}
                  </Text>
                </View>
              </View>

              <Text style={estilos.meta}>
                {item.rota_turno} · {item.total_alunos} aluno{item.total_alunos === 1 ? "" : "s"}
              </Text>

              <Botao56
                titulo={
                  item.status === "planejada"
                    ? "Iniciar turno"
                    : finalizada
                      ? "Ver viagem"
                      : "Continuar viagem"
                }
                onPress={() => void abrirViagem(item)}
                carregando={iniciandoId === item.id}
                variante={finalizada ? "secundario" : "primario"}
                tamanho={emAndamento ? "grande" : "min"}
                estilo={estilos.botaoAbrir}
              />
            </View>
          );
        }}
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
      flexDirection: "row",
      alignItems: "center",
      paddingHorizontal: espacamento.lg,
      paddingBottom: espacamento.md,
    },
    cabecalhoInfo: {
      flex: 1,
    },
    saudacao: {
      fontSize: tipografia.destaque,
      fontWeight: peso.forte,
      color: cores.tinta,
    },
    contagem: {
      fontSize: tipografia.endereco,
      color: cores.esmaecido,
      marginTop: 1,
    },
    botaoPrefs: {
      width: TOQUE_MIN,
      height: TOQUE_MIN,
      alignItems: "center",
      justifyContent: "center",
      gap: 4,
    },
    botaoPrefsPressionado: {
      opacity: 0.6,
    },
    barraIcone: {
      height: 2,
      borderRadius: raio.pilula,
      backgroundColor: cores.esmaecido,
    },
    barraLonga: {
      width: 20,
    },
    barraMedia: {
      width: 14,
    },
    barraCurta: {
      width: 9,
    },
    lista: {
      padding: espacamento.lg,
      flexGrow: 1,
    },
    vazio: {
      color: cores.dica,
      textAlign: "center",
      marginTop: espacamento.xl,
      fontSize: tipografia.endereco,
    },
    cartao: {
      backgroundColor: cores.cartao,
      borderRadius: raio.lg,
      borderWidth: 1,
      borderColor: cores.linha,
      padding: espacamento.lg,
      marginBottom: espacamento.md,
    },
    cartaoAtivo: {
      borderColor: cores.marca,
      borderWidth: 2,
    },
    cartaoTopo: {
      flexDirection: "row",
      alignItems: "flex-start",
      gap: espacamento.sm,
    },
    nomeRota: {
      flex: 1,
      fontSize: tipografia.subtitulo,
      fontWeight: peso.forte,
      color: cores.tinta,
    },
    nomeRotaFinalizada: {
      color: cores.esmaecido,
    },
    selo: {
      borderRadius: raio.pilula,
      borderWidth: 1,
      paddingVertical: 4,
      paddingHorizontal: 10,
    },
    seloAtivo: {
      backgroundColor: cores.marcaSuave,
      borderColor: cores.marcaBorda,
    },
    seloPlanejado: {
      backgroundColor: cores.neutroSuave,
      borderColor: cores.linha2,
    },
    seloFeito: {
      backgroundColor: cores.neutroSuave,
      borderColor: cores.linha2,
    },
    seloTexto: {
      fontSize: tipografia.legenda,
      fontWeight: peso.forte,
      letterSpacing: ESPACO_LETRA_SELO,
    },
    seloTextoAtivo: {
      color: cores.marca,
    },
    seloTextoPlanejado: {
      color: cores.esmaecido,
    },
    seloTextoFeito: {
      color: cores.esmaecido,
    },
    meta: {
      fontSize: tipografia.endereco,
      color: cores.esmaecido,
      marginTop: espacamento.xs,
      marginBottom: espacamento.lg,
    },
    botaoAbrir: {
      marginTop: 0,
    },
  });
