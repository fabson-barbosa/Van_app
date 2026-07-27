/**
 * Stack única, sem bottom nav (Alunos/Frota/Perfil/Emergência/Broadcast do
 * protótipo antigo são do plano superado — CLAUDE.md §10/§11, fora de
 * escopo do B4).
 *
 *   não autenticado -> Login
 *   autenticado     -> RotaDoDia -> Viagem -> FinalizarViagem
 *
 * `sessaoExpirada` (ver AuthContext) renderiza um prompt de reautenticação
 * POR CIMA da tela atual em vez de navegar pra longe — preserva o estado da
 * viagem em andamento enquanto o motorista loga de novo.
 */
import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import React, { useEffect, useState } from "react";
import { ActivityIndicator, Modal, StyleSheet, Text, View } from "react-native";

import { useAuth } from "../shared/auth/AuthContext";
import { iniciarDrenagemAutomatica } from "../shared/offline/sync";
import { cores, espacamento } from "../shared/theme";
import { LoginScreen } from "../motorista/screens/LoginScreen";
import { RotaDoDiaScreen } from "../motorista/screens/RotaDoDiaScreen";
import { ViagemScreen } from "../motorista/screens/ViagemScreen";
import { FinalizarViagemScreen } from "../motorista/screens/FinalizarViagemScreen";

export type RootStackParamList = {
  Login: undefined;
  RotaDoDia: undefined;
  Viagem: { viagemId: string };
  FinalizarViagem: { viagemId: string };
};

const Stack = createNativeStackNavigator<RootStackParamList>();

export function RootNavigator(): React.JSX.Element {
  const { token, carregando } = useAuth();

  useEffect(() => {
    const parar = iniciarDrenagemAutomatica();
    return parar;
  }, []);

  if (carregando) {
    return (
      <View style={estilos.carregando}>
        <ActivityIndicator size="large" color={cores.marca} />
      </View>
    );
  }

  return (
    <NavigationContainer>
      <Stack.Navigator screenOptions={{ headerShown: false }}>
        {token == null ? (
          <Stack.Screen name="Login" component={LoginScreen} />
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
    } catch {
      setErro("E-mail ou senha inválidos.");
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
