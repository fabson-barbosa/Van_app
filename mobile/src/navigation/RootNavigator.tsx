/**
 * Stack única, sem bottom nav (Alunos/Frota/Perfil/Emergência/Broadcast do
 * protótipo antigo são do plano superado — CLAUDE.md §10/§11, fora de
 * escopo do B4).
 *
 *   não autenticado          -> Login
 *   autenticado, motorista*  -> RotaDoDia -> Viagem -> FinalizarViagem
 *   autenticado, responsavel -> ListaFilhos -> AcompanharFilho / HistoricoFilho
 *
 * Bloco B5: uma única app Expo pras duas experiências (decisão registrada em
 * PROGRESSO.md/ARQUITETURA.md — CLAUDE.md fala em "três apps" mas o pedido
 * explícito deste bloco foi reaproveitar `mobile/src/shared`, e não há
 * tooling de monorepo no projeto pra justificar um segundo projeto Expo). O
 * `role` vem da claim do JWT (`AuthContext`, decodificado só pra escolher a
 * stack — nunca é fonte de autorização, isso é sempre o backend).
 *
 * `sessaoExpirada` (ver AuthContext) renderiza um prompt de reautenticação
 * POR CIMA da tela atual em vez de navegar pra longe — preserva o estado da
 * viagem/tela em andamento enquanto o usuário loga de novo.
 */
import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import React, { useEffect, useState } from "react";
import { ActivityIndicator, Modal, StyleSheet, Text, View } from "react-native";

import { AcompanharFilhoScreen } from "../responsavel/screens/AcompanharFilhoScreen";
import { HistoricoFilhoScreen } from "../responsavel/screens/HistoricoFilhoScreen";
import { ListaFilhosScreen } from "../responsavel/screens/ListaFilhosScreen";
import { useAuth } from "../shared/auth/AuthContext";
import { iniciarDrenagemAutomatica } from "../shared/offline/sync";
import { LoginScreen, mensagemErroLogin } from "../shared/screens/LoginScreen";
import { cores, espacamento } from "../shared/theme";
import { FinalizarViagemScreen } from "../motorista/screens/FinalizarViagemScreen";
import { RotaDoDiaScreen } from "../motorista/screens/RotaDoDiaScreen";
import { ViagemScreen } from "../motorista/screens/ViagemScreen";
import { inicializarNotificacoes } from "../shared/notifications";
import { navigationRef } from "./navigationRef";
import type { RootStackParamList } from "./types";

export type { RootStackParamList };

const Stack = createNativeStackNavigator<RootStackParamList>();

export function RootNavigator(): React.JSX.Element {
  const { token, role, carregando } = useAuth();

  useEffect(() => {
    const parar = iniciarDrenagemAutomatica();
    return parar;
  }, []);

  useEffect(() => {
    if (!token) return undefined;
    return inicializarNotificacoes();
  }, [token]);

  if (carregando) {
    return (
      <View style={estilos.carregando}>
        <ActivityIndicator size="large" color={cores.marca} />
      </View>
    );
  }

  return (
    <NavigationContainer ref={navigationRef}>
      <Stack.Navigator screenOptions={{ headerShown: false }}>
        {token == null ? (
          <Stack.Screen name="Login" component={LoginScreen} />
        ) : role === "responsavel" ? (
          <>
            <Stack.Screen name="ListaFilhos" component={ListaFilhosScreen} />
            <Stack.Screen name="AcompanharFilho" component={AcompanharFilhoScreen} />
            <Stack.Screen name="HistoricoFilho" component={HistoricoFilhoScreen} />
          </>
        ) : (
          <>
            <Stack.Screen name="RotaDoDia" component={RotaDoDiaScreen} />
            <Stack.Screen name="Viagem" component={ViagemScreen} />
            <Stack.Screen name="FinalizarViagem" component={FinalizarViagemScreen} />
          </>
        )}
      </Stack.Navigator>
      <PromptReautenticacao />
    </NavigationContainer>
  );
}

function PromptReautenticacao(): React.JSX.Element | null {
  const { sessaoExpirada, login } = useAuth();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  if (!sessaoExpirada) return null;

  const entrar = async () => {
    setEnviando(true);
    setErro(null);
    try {
      await login(email, senha);
      setEmail("");
      setSenha("");
    } catch (e) {
      setErro(mensagemErroLogin(e));
    } finally {
      setEnviando(false);
    }
  };

  // Reaproveita o formulário simples do LoginScreen num modal — os eventos
  // já enfileirados continuam intactos e a fila retoma sozinha (ver
  // AuthContext::login -> retomarAposRelogin()).
  return (
    <Modal visible transparent animationType="fade">
      <View style={estilos.fundoModal}>
        <View style={estilos.cartaoModal}>
          <Text style={estilos.titulo}>Sessão expirada</Text>
          <Text style={estilos.subtitulo}>Faça login de novo. Nada da viagem foi perdido.</Text>
          <LoginScreen
            embutido
            email={email}
            senha={senha}
            onMudarEmail={setEmail}
            onMudarSenha={setSenha}
            onEntrar={entrar}
            enviando={enviando}
            erro={erro}
          />
        </View>
      </View>
    </Modal>
  );
}

const estilos = StyleSheet.create({
  carregando: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: cores.papel,
  },
  fundoModal: {
    flex: 1,
    backgroundColor: "rgba(16,35,30,0.7)",
    alignItems: "center",
    justifyContent: "center",
    padding: espacamento.xl,
  },
  cartaoModal: {
    width: "100%",
    maxWidth: 380,
    backgroundColor: cores.papel,
    borderRadius: 20,
    padding: espacamento.xl,
  },
  titulo: {
    fontSize: 20,
    fontWeight: "700",
    color: cores.tinta,
    textAlign: "center",
  },
  subtitulo: {
    fontSize: 13,
    color: cores.esmaecido,
    textAlign: "center",
    marginTop: espacamento.xs,
    marginBottom: espacamento.lg,
  },
});
