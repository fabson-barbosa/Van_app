/** Tela 1 — lista de filhos com o estado atual de cada um (Bloco B5). */
import React, { useCallback, useEffect, useState } from "react";
import { useFocusEffect } from "@react-navigation/native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { FlatList, Pressable, RefreshControl, StyleSheet, Text, View } from "react-native";

import { ApiError, NetworkError } from "../../shared/api/client";
import { endpoints } from "../../shared/api/endpoints";
import type { FilhoOut, StatusFilhoOut } from "../../shared/api/types";
import { useAuth } from "../../shared/auth/AuthContext";
import { EstadoBadge } from "../../shared/components/EstadoBadge";
import { cores, espacamento, raio, tipografia } from "../../shared/theme";
import type { RootStackParamList } from "../../navigation/types";

type Props = NativeStackScreenProps<RootStackParamList, "ListaFilhos">;

export function ListaFilhosScreen({ navigation }: Props): React.JSX.Element {
  const { logout, token } = useAuth();
  const [filhos, setFilhos] = useState<FilhoOut[]>([]);
  const [statusPorAluno, setStatusPorAluno] = useState<Record<string, StatusFilhoOut>>({});
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    setErro(null);
    try {
      const lista = await endpoints.listarFilhos();
      setFilhos(lista);
      // Status é por filho (sem endpoint em lote — LGPD/escopo já filtra o
      // suficiente pra isso não ser um N+1 de verdade: são poucos filhos por
      // responsável). Falha isolada de UM filho não derruba a lista inteira.
      const resultados = await Promise.all(
        lista.map(async (f) => {
          try {
            return [f.aluno_id, await endpoints.statusFilho(f.aluno_id)] as const;
          } catch {
            return null;
          }
        })
      );
      const mapa: Record<string, StatusFilhoOut> = {};
      for (const resultado of resultados) {
        if (resultado) mapa[resultado[0]] = resultado[1];
      }
      setStatusPorAluno(mapa);
    } catch (e) {
      setErro(
        e instanceof NetworkError
          ? "Sem conexão — verifique o sinal e tente de novo."
          : e instanceof ApiError
            ? e.detail
            : "Não foi possível carregar seus filhos."
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

  // Mesmo achado do B4 (RotaDoDiaScreen): `useFocusEffect` não retrigga
  // sozinho quando a sessão é renovada pelo modal de reautenticação (ele
  // fica por cima desta tela, sem tirar o foco dela).
  useEffect(() => {
    if (token) void carregar();
  }, [token, carregar]);

  return (
    <View style={estilos.tela}>
      <View style={estilos.cabecalho}>
        <Text style={estilos.titulo}>Meus filhos</Text>
        <Text style={estilos.sair} onPress={() => void logout()}>
          Sair
        </Text>
      </View>

      {erro ? <Text style={estilos.erro}>{erro}</Text> : null}

      <FlatList
        data={filhos}
        keyExtractor={(f) => f.aluno_id}
        contentContainerStyle={estilos.lista}
        refreshControl={<RefreshControl refreshing={carregando} onRefresh={carregar} />}
        ListEmptyComponent={
          !carregando ? <Text style={estilos.vazio}>Nenhum filho vinculado à sua conta.</Text> : null
        }
        renderItem={({ item }) => {
          const status = statusPorAluno[item.aluno_id];
          return (
            <Pressable
              style={estilos.cartao}
              onPress={() => navigation.navigate("AcompanharFilho", { alunoId: item.aluno_id, nome: item.nome })}
            >
              <View style={estilos.linhaCartao}>
                <Text style={estilos.nome}>{item.nome}</Text>
                {status?.tem_viagem_hoje && status.estado ? (
                  <EstadoBadge estado={status.estado} />
                ) : (
                  <Text style={estilos.semViagem}>Sem rota hoje</Text>
                )}
              </View>
              {item.parada_endereco ? (
                <Text style={estilos.endereco} numberOfLines={1}>
                  {item.parada_endereco}
                </Text>
              ) : null}
            </Pressable>
          );
        }}
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
    paddingTop: espacamento.xl,
    paddingBottom: espacamento.md,
  },
  titulo: {
    fontSize: tipografia.titulo,
    fontWeight: "700",
    color: cores.tinta,
  },
  sair: {
    fontSize: 13,
    color: cores.esmaecido,
    fontWeight: "600",
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
    minHeight: 56,
  },
  linhaCartao: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  nome: {
    fontSize: 16,
    fontWeight: "700",
    color: cores.tinta,
  },
  semViagem: {
    fontSize: 11.5,
    color: cores.dica,
    fontWeight: "600",
  },
  endereco: {
    fontSize: 12.5,
    color: cores.esmaecido,
    marginTop: 2,
  },
});
