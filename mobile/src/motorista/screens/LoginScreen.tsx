/** Tela 1 — Login. Também reaproveitada (modo `embutido`) no prompt de
 * reautenticação do RootNavigator quando a sessão expira em campo. */
import React, { useState } from "react";
import { KeyboardAvoidingView, Platform, StyleSheet, Text, TextInput, View } from "react-native";

import { Botao56 } from "../../shared/components/Botao56";
import { useAuth } from "../../shared/auth/AuthContext";
import { cores, espacamento, raio, tipografia } from "../../shared/theme";

// Sem `navigation`/`route`: esta tela nunca navega sozinha — o
// RootNavigator troca de stack sozinho reagindo ao `token` do AuthContext
// (ver navigation/RootNavigator.tsx). Isso também é o que permite reusar o
// mesmo componente, sem adaptação, dentro do modal de reautenticação.
interface Props {
  embutido?: boolean;
  email?: string;
  senha?: string;
  onMudarEmail?: (valor: string) => void;
  onMudarSenha?: (valor: string) => void;
  onEntrar?: () => void;
  enviando?: boolean;
  erro?: string | null;
}

export function LoginScreen(props: Props): React.JSX.Element {
  if (props.embutido) return <Formulario {...props} />;
  return <TelaCompleta />;
}

function TelaCompleta(): React.JSX.Element {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const entrar = async () => {
    setEnviando(true);
    setErro(null);
    try {
      await login(email, senha);
    } catch {
      setErro("E-mail ou senha inválidos.");
    } finally {
      setEnviando(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={estilos.tela}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <View style={estilos.cabecalho}>
        <Text style={estilos.logo}>🚌</Text>
        <Text style={estilos.marca}>VaiVem</Text>
        <Text style={estilos.tagline}>Transporte escolar seguro</Text>
      </View>
      <Formulario
        email={email}
        senha={senha}
        onMudarEmail={setEmail}
        onMudarSenha={setSenha}
        onEntrar={entrar}
        enviando={enviando}
        erro={erro}
      />
    </KeyboardAvoidingView>
  );
}

function Formulario({
  email = "",
  senha = "",
  onMudarEmail,
  onMudarSenha,
  onEntrar,
  enviando = false,
  erro = null,
}: Pick<Props, "email" | "senha" | "onMudarEmail" | "onMudarSenha" | "onEntrar" | "enviando" | "erro">): React.JSX.Element {
  const podeEntrar = email.trim().length > 0 && senha.length > 0 && !enviando;

  return (
    <View style={estilos.formulario}>
      <TextInput
        style={estilos.campo}
        placeholder="E-mail"
        placeholderTextColor={cores.dica}
        autoCapitalize="none"
        autoComplete="email"
        keyboardType="email-address"
        value={email}
        onChangeText={onMudarEmail}
        editable={!enviando}
      />
      <TextInput
        style={estilos.campo}
        placeholder="Senha"
        placeholderTextColor={cores.dica}
        secureTextEntry
        autoComplete="password"
        value={senha}
        onChangeText={onMudarSenha}
        editable={!enviando}
        onSubmitEditing={onEntrar}
      />
      {erro ? <Text style={estilos.erro}>{erro}</Text> : null}
      <Botao56
        titulo="Entrar"
        onPress={() => onEntrar?.()}
        desabilitado={!podeEntrar}
        carregando={enviando}
        estilo={estilos.botaoEntrar}
      />
    </View>
  );
}

const estilos = StyleSheet.create({
  tela: {
    flex: 1,
    backgroundColor: cores.marca,
    alignItems: "center",
    justifyContent: "center",
    padding: espacamento.xl,
  },
  cabecalho: {
    alignItems: "center",
    marginBottom: espacamento.xl,
  },
  logo: {
    fontSize: 40,
  },
  marca: {
    fontSize: 30,
    fontWeight: "700",
    color: "#ffffff",
    marginTop: espacamento.sm,
  },
  tagline: {
    fontSize: 14,
    color: "rgba(255,255,255,0.85)",
    marginTop: 2,
  },
  formulario: {
    width: "100%",
    maxWidth: 360,
    gap: espacamento.sm,
  },
  campo: {
    minHeight: 50,
    backgroundColor: "rgba(255,255,255,0.96)",
    borderRadius: raio.md,
    paddingHorizontal: espacamento.lg,
    fontSize: tipografia.corpo,
    color: cores.tinta,
  },
  erro: {
    color: "#ffd9d9",
    fontSize: 13,
    fontWeight: "600",
    textAlign: "center",
  },
  botaoEntrar: {
    marginTop: espacamento.xs,
  },
});
