/** Tela 2 — acompanhamento (mapa VIRTUAL): progresso por paradas, nunca
 * coordenada (CLAUDE.md §2/§10). O timer de "chegamos, esperando há N min"
 * é client-side (JS puro, tela aberta) — a notificação persistente do SO
 * (fora do app) é o resumo aproximado, ver `shared/notifications/persistente.ts`. */
import React, { useCallback, useEffect, useState } from "react";
import { useFocusEffect } from "@react-navigation/native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";

import { ApiError, NetworkError } from "../../shared/api/client";
import { endpoints } from "../../shared/api/endpoints";
import type { StatusFilhoOut } from "../../shared/api/types";
import { useAuth } from "../../shared/auth/AuthContext";
import { Botao56 } from "../../shared/components/Botao56";
import { EstadoBadge } from "../../shared/components/EstadoBadge";
import { cores, espacamento, raio, tipografia } from "../../shared/theme";
import type { RootStackParamList } from "../../navigation/types";
import { BarraProgresso } from "../components/BarraProgresso";

type Props = NativeStackScreenProps<RootStackParamList, "AcompanharFilho">;

const INTERVALO_ATUALIZACAO_MS = 20_000;
const INTERVALO_TIMER_MS = 15_000; // não precisa de precisão de segundo — só o texto "há N min"

function minutosDecorridos(chegouEmIso: string, agora: number): number {
  return Math.max(0, Math.floor((agora - new Date(chegouEmIso).getTime()) / 60_000));
}

export function AcompanharFilhoScreen({ route, navigation }: Props): React.JSX.Element {
  const { alunoId, nome: nomeDaRota } = route.params;
  const { token } = useAuth();

  const [nome, setNome] = useState(nomeDaRota ?? "");
  const [status, setStatus] = useState<StatusFilhoOut | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [agora, setAgora] = useState(() => Date.now());

  const carregar = useCallback(async () => {
    setErro(null);
    try {
      if (!nomeDaRota) {
        // Chegou aqui por toque numa notificação (sem nome no payload por
        // minimização) — resolve sozinho.
        const filhos = await endpoints.listarFilhos();
        const encontrado = filhos.find((f) => f.aluno_id === alunoId);
        if (encontrado) setNome(encontrado.nome);
      }
      const resultado = await endpoints.statusFilho(alunoId);
      setStatus(resultado);
    } catch (e) {
      setErro(
        e instanceof NetworkError
          ? "Sem conexão — mostrando os últimos dados carregados."
          : e instanceof ApiError
            ? e.detail
            : "Não foi possível carregar o acompanhamento."
      );
    } finally {
      setCarregando(false);
    }
  }, [alunoId, nomeDaRota]);

  useFocusEffect(
    useCallback(() => {
      void carregar();
    }, [carregar])
  );

  useEffect(() => {
    if (token) void carregar();
  }, [token, carregar]);

  // Atualiza sozinho enquanto a rota está em andamento — sem isso o
  // responsável precisaria puxar pra atualizar toda hora pra ver a van
  // "andar" pelas paradas.
  useEffect(() => {
    if (status?.viagem_status !== "em_andamento") return undefined;
    const intervalo = setInterval(() => void carregar(), INTERVALO_ATUALIZACAO_MS);
    return () => clearInterval(intervalo);
  }, [status?.viagem_status, carregar]);

  useEffect(() => {
    if (status?.estado !== "chegou") return undefined;
    const intervalo = setInterval(() => setAgora(Date.now()), INTERVALO_TIMER_MS);
    return () => clearInterval(intervalo);
  }, [status?.estado]);

  return (
    <View style={estilos.tela}>
      <View style={estilos.cabecalho}>
        <Text style={estilos.voltar} onPress={() => navigation.goBack()}>
          ‹ Filhos
        </Text>
        <Text style={estilos.nome} numberOfLines={1}>
          {nome || "Acompanhar"}
        </Text>
      </View>

      <ScrollView
        contentContainerStyle={estilos.corpo}
        refreshControl={<RefreshControl refreshing={carregando} onRefresh={carregar} />}
      >
        {erro ? <Text style={estilos.erro}>{erro}</Text> : null}

        {carregando && !status ? (
          <ActivityIndicator color={cores.marca} style={estilos.spinner} />
        ) : !status?.tem_viagem_hoje ? (
          <View style={estilos.cartao}>
            <Text style={estilos.textoCentro}>Sem viagem hoje para {nome || "este aluno"}.</Text>
          </View>
        ) : (
          <>
            <View style={estilos.cartao}>
              <View style={estilos.linhaEstado}>
                {status.estado ? <EstadoBadge estado={status.estado} /> : null}
              </View>

              {status.viagem_status === "planejada" ? (
                <Text style={estilos.mensagem}>A van ainda não saiu — a rota vai começar em breve.</Text>
              ) : status.viagem_status === "finalizada" ? (
                <Text style={estilos.mensagem}>A rota de hoje já terminou.</Text>
              ) : (
                <>
                  {status.paradas_totais != null &&
                  status.paradas_concluidas != null &&
                  status.paradas_restantes != null ? (
                    <BarraProgresso
                      paradasTotais={status.paradas_totais}
                      paradasConcluidas={status.paradas_concluidas}
                      paradasRestantes={status.paradas_restantes}
                    />
                  ) : null}

                  {status.estado === "chegou" && status.chegou_em ? (
                    <View style={estilos.bannerChegada}>
                      <Text style={estilos.bannerChegadaTitulo}>Chegamos! Estamos esperando.</Text>
                      <Text style={estilos.bannerChegadaTexto}>
                        Há {minutosDecorridos(status.chegou_em, agora)} min
                      </Text>
                    </View>
                  ) : null}

                  {status.estado === "aguardando" && status.faixa_min_baixo != null && status.faixa_min_alto != null ? (
                    <Text style={estilos.mensagem}>
                      Chegada estimada em {status.faixa_min_baixo}–{status.faixa_min_alto} min.
                    </Text>
                  ) : null}

                  {status.estado === "a_bordo" ? (
                    <Text style={estilos.mensagem}>A bordo, a caminho do destino.</Text>
                  ) : null}
                  {status.estado === "entregue" ? <Text style={estilos.mensagem}>Entregue com sucesso.</Text> : null}
                  {status.estado === "ausente" ? (
                    <Text style={estilos.mensagem}>Marcado(a) como ausente hoje.</Text>
                  ) : null}
                </>
              )}
            </View>

            <Botao56
              titulo="Ver histórico de hoje"
              variante="secundario"
              onPress={() => navigation.navigate("HistoricoFilho", { alunoId, nome })}
            />
          </>
        )}
      </ScrollView>
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
  voltar: {
    fontSize: 13,
    color: cores.info,
    fontWeight: "600",
    marginBottom: espacamento.xs,
  },
  nome: {
    fontSize: tipografia.titulo,
    fontWeight: "700",
    color: cores.tinta,
  },
  corpo: {
    padding: espacamento.lg,
    gap: espacamento.md,
  },
  erro: {
    color: cores.perigo,
    fontSize: 13,
    fontWeight: "600",
    marginBottom: espacamento.sm,
  },
  spinner: {
    marginTop: espacamento.xl,
  },
  cartao: {
    backgroundColor: cores.cartao,
    borderRadius: raio.lg,
    borderWidth: 1,
    borderColor: cores.linha,
    padding: espacamento.lg,
    gap: espacamento.md,
  },
  linhaEstado: {
    flexDirection: "row",
  },
  textoCentro: {
    fontSize: tipografia.corpo,
    color: cores.esmaecido,
    textAlign: "center",
  },
  mensagem: {
    fontSize: tipografia.corpo,
    color: cores.tinta,
  },
  bannerChegada: {
    backgroundColor: cores.marcaSuave,
    borderRadius: raio.md,
    padding: espacamento.md,
  },
  bannerChegadaTitulo: {
    fontSize: 15,
    fontWeight: "700",
    color: cores.marca,
  },
  bannerChegadaTexto: {
    fontSize: 13,
    color: cores.marca,
    marginTop: 2,
  },
});
