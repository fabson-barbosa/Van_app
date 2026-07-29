/** Tela 2 — Rota do dia: viagens da jornada do motorista, iniciar viagem. */
import React, { useCallback, useEffect, useState } from "react";
import { useFocusEffect } from "@react-navigation/native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { FlatList, RefreshControl, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Botao56 } from "../../shared/components/Botao56";
import { LinkToque } from "../../shared/components/LinkToque";
import { ApiError, NetworkError } from "../../shared/api/client";
import { endpoints } from "../../shared/api/endpoints";
import type { ViagemOut } from "../../shared/api/types";
import { useAuth } from "../../shared/auth/AuthContext";
import { cores, espacamento, raio, tipografia } from "../../shared/theme";
import type { RootStackParamList } from "../../navigation/RootNavigator";

type Props = NativeStackScreenProps<RootStackParamList, "RotaDoDia">;

const ROTULO_STATUS: Record<ViagemOut["status"], string> = {
  planejada: "Planejada",
  em_andamento: "Em andamento",
  finalizada: "Finalizada",
};

export function RotaDoDiaScreen({ navigation }: Props): React.JSX.Element {
  const { logout, token } = useAuth();
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

  // `useFocusEffect` só reage a eventos de navegação — o modal de
  // reautenticação (RootNavigator) fica POR CIMA desta tela sem tirar o
  // foco dela, então logar de novo não retriggava esse efeito e a lista
  // ficava presa no erro/estado vazio da primeira busca (feita com o token
  // vencido). Achado testando em aparelho físico real: precisava de um
  // "puxar para atualizar" manual depois de reautenticar. Este efeito extra
  // busca de novo sempre que o token muda de verdade (login inicial e
  // qualquer reautenticação).
  useEffect(() => {
    if (token) void carregar();
  }, [token, carregar]);

  const abrirViagem = async (viagem: ViagemOut) => {
    if (viagem.status === "planejada") {
      setIniciandoId(viagem.id);
      try {
        await endpoints.iniciarViagem(viagem.id);
      } catch (e) {
        setIniciandoId(null);
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
        <Text style={estilos.saudacao}>Rota do dia</Text>
        <LinkToque titulo="Sair" cor={cores.esmaecido} onPress={() => void logout()} />
      </View>

      {erro ? <Text style={estilos.erro}>{erro}</Text> : null}

      <FlatList
        data={viagens}
        keyExtractor={(v) => v.id}
        contentContainerStyle={[estilos.lista, { paddingBottom: espacamento.lg + insets.bottom }]}
        refreshControl={<RefreshControl refreshing={carregando} onRefresh={carregar} />}
        ListEmptyComponent={
          !carregando ? <Text style={estilos.vazio}>Nenhuma viagem para hoje.</Text> : null
        }
        renderItem={({ item }) => (
          <View style={estilos.cartao}>
            <Text style={estilos.nomeRota}>{item.rota_nome}</Text>
            <Text style={estilos.meta}>
              {item.rota_turno} · {item.total_alunos} aluno{item.total_alunos === 1 ? "" : "s"} ·{" "}
              {ROTULO_STATUS[item.status]}
            </Text>
            <Botao56
              titulo={item.status === "planejada" ? "Iniciar turno" : "Abrir viagem"}
              onPress={() => void abrirViagem(item)}
              carregando={iniciandoId === item.id}
              variante={item.status === "finalizada" ? "secundario" : "primario"}
              estilo={estilos.botaoAbrir}
            />
          </View>
        )}
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
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: espacamento.lg,
    paddingBottom: espacamento.md,
  },
  saudacao: {
    fontSize: tipografia.titulo,
    fontWeight: "700",
    color: cores.tinta,
  },
  erro: {
    color: cores.perigo,
    fontSize: 13,
    fontWeight: "600",
    paddingHorizontal: espacamento.lg,
    marginBottom: espacamento.sm,
  },
  lista: {
    padding: espacamento.lg,
    gap: espacamento.md,
    flexGrow: 1,
  },
  vazio: {
    color: cores.dica,
    textAlign: "center",
    marginTop: espacamento.xl,
  },
  cartao: {
    backgroundColor: cores.cartao,
    borderRadius: raio.lg,
    borderWidth: 1,
    borderColor: cores.linha,
    padding: espacamento.lg,
    marginBottom: espacamento.md,
  },
  nomeRota: {
    fontSize: 16,
    fontWeight: "700",
    color: cores.tinta,
  },
  meta: {
    fontSize: 12.5,
    color: cores.esmaecido,
    marginTop: 2,
    marginBottom: espacamento.md,
  },
  botaoAbrir: {
    marginTop: espacamento.xs,
  },
});
