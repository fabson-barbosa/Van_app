/** Tela 3 — histórico simples do dia: o que aconteceu com o filho. */
import React, { useCallback, useEffect, useState } from "react";
import { useFocusEffect } from "@react-navigation/native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { FlatList, RefreshControl, StyleSheet, Text, View } from "react-native";

import { ApiError, NetworkError } from "../../shared/api/client";
import { endpoints } from "../../shared/api/endpoints";
import type { EventoHistoricoOut, TipoEventoHistorico } from "../../shared/api/types";
import { useAuth } from "../../shared/auth/AuthContext";
import { cores, espacamento, raio, tipografia } from "../../shared/theme";
import type { RootStackParamList } from "../../navigation/types";

type Props = NativeStackScreenProps<RootStackParamList, "HistoricoFilho">;

const ROTULO_EVENTO: Record<TipoEventoHistorico, string> = {
  cheguei: "A van chegou na parada",
  checkin: "Embarcou na van",
  checkout: "Desembarcou no destino",
  ausente: "Marcado(a) como ausente",
};

function formatarHorario(iso: string): string {
  return new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

export function HistoricoFilhoScreen({ route }: Props): React.JSX.Element {
  const { alunoId, nome } = route.params;
  const { token } = useAuth();

  const [eventos, setEventos] = useState<EventoHistoricoOut[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    setErro(null);
    try {
      setEventos(await endpoints.historicoFilho(alunoId));
    } catch (e) {
      setErro(
        e instanceof NetworkError
          ? "Sem conexão — verifique o sinal e tente de novo."
          : e instanceof ApiError
            ? e.detail
            : "Não foi possível carregar o histórico."
      );
    } finally {
      setCarregando(false);
    }
  }, [alunoId]);

  useFocusEffect(
    useCallback(() => {
      void carregar();
    }, [carregar])
  );

  useEffect(() => {
    if (token) void carregar();
  }, [token, carregar]);

  return (
    <View style={estilos.tela}>
      <View style={estilos.cabecalho}>
        <Text style={estilos.titulo}>Histórico de hoje</Text>
        {nome ? <Text style={estilos.subtitulo}>{nome}</Text> : null}
      </View>

      {erro ? <Text style={estilos.erro}>{erro}</Text> : null}

      <FlatList
        data={eventos}
        keyExtractor={(_, indice) => String(indice)}
        contentContainerStyle={estilos.lista}
        refreshControl={<RefreshControl refreshing={carregando} onRefresh={carregar} />}
        ListEmptyComponent={
          !carregando ? <Text style={estilos.vazio}>Nada registrado ainda hoje.</Text> : null
        }
        renderItem={({ item }) => (
          <View style={estilos.linha}>
            <Text style={estilos.horario}>{formatarHorario(item.ocorrido_em)}</Text>
            <Text style={estilos.descricao}>{ROTULO_EVENTO[item.tipo]}</Text>
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
    paddingHorizontal: espacamento.lg,
    paddingTop: espacamento.xl,
    paddingBottom: espacamento.md,
  },
  titulo: {
    fontSize: tipografia.titulo,
    fontWeight: "700",
    color: cores.tinta,
  },
  subtitulo: {
    fontSize: 13,
    color: cores.esmaecido,
    marginTop: 2,
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
  },
  vazio: {
    color: cores.dica,
    textAlign: "center",
    marginTop: espacamento.xl,
  },
  linha: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: cores.cartao,
    borderRadius: raio.md,
    borderWidth: 1,
    borderColor: cores.linha,
    paddingVertical: espacamento.md,
    paddingHorizontal: espacamento.lg,
    marginBottom: espacamento.sm,
    minHeight: 56,
  },
  horario: {
    fontSize: 13,
    fontWeight: "700",
    color: cores.marca,
    width: 56,
  },
  descricao: {
    fontSize: tipografia.corpo,
    color: cores.tinta,
    flex: 1,
  },
});
