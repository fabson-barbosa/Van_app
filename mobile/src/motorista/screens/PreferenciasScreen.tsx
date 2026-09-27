/**
 * Tela 5 — Preferências do motorista (Bloco B8).
 *
 * Existe porque duas coisas novas precisam ser escolhidas por quem usa o app, e
 * nenhuma delas cabe no meio de uma viagem: o tema (claro/escuro/automático) e o
 * som de confirmação. O B4 tinha descartado "Perfil" do protótipo antigo por ser
 * do plano superado (CLAUDE.md §11) — esta tela não é aquela: não tem cadastro,
 * não tem dado de aluno, tem dois controles e o botão de sair.
 *
 * "Sair" mudou de lugar: estava no cabeçalho da Rota do Dia, a poucos dp do botão
 * que inicia o turno. Sair é destrutivo na prática (derruba a sessão com a fila
 * offline dentro dela) e é usado uma vez por dia, ou menos — não tem por que
 * dividir a barra superior com a ação mais frequente da tela.
 *
 * Cada opção de tema mostra a paleta que aplica, em duas amostras. Sem isso, num
 * app cuja tela principal é outra, escolher "Escuro" é apostar no escuro — e o
 * motorista teria que sair daqui, olhar, e voltar.
 */
import React, { useEffect, useState } from "react";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { Pressable, ScrollView, StyleSheet, Switch, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Botao56 } from "../../shared/components/Botao56";
import { useAuth } from "../../shared/auth/AuthContext";
import { assinarSom, definirSom, feedbackAceito, somLigado } from "../../shared/feedback";
import {
  ESPACO_LETRA_SELO,
  type ModoTema,
  type Paleta,
  TOQUE_MIN,
  espacamento,
  paletas,
  peso,
  raio,
  tipografia,
  useEstilos,
  useTema,
} from "../../shared/theme";
import type { RootStackParamList } from "../../navigation/RootNavigator";

type Props = NativeStackScreenProps<RootStackParamList, "Preferencias">;

const OPCOES_TEMA: { modo: ModoTema; titulo: string; descricao: string }[] = [
  { modo: "automatico", titulo: "Automático", descricao: "Acompanha o Android" },
  { modo: "claro", titulo: "Claro", descricao: "Melhor sob sol direto" },
  { modo: "escuro", titulo: "Escuro", descricao: "Menos ofuscante de noite" },
];

export function PreferenciasScreen({ navigation }: Props): React.JSX.Element {
  const { cores, modo, modoEfetivo, definirModo } = useTema();
  const estilos = useEstilos(criarEstilos, cores);
  const insets = useSafeAreaInsets();
  const { logout } = useAuth();
  const [som, setSom] = useState(() => somLigado());

  // A preferência de som vive num módulo (é lida de handlers de toque, sem
  // await), então a tela se inscreve nela em vez de ser a dona.
  useEffect(() => assinarSom(setSom), []);

  function alternarSom(novo: boolean) {
    definirSom(novo);
    // Tocar a amostra ao LIGAR é o próprio teste do recurso: o motorista
    // descobre aqui, parado, como soa — e não no meio da rota.
    if (novo) feedbackAceito();
  }

  return (
    <ScrollView
      style={estilos.tela}
      contentContainerStyle={[
        estilos.conteudo,
        { paddingTop: espacamento.lg + insets.top, paddingBottom: espacamento.xl + insets.bottom },
      ]}
    >
      <Text style={estilos.titulo}>Preferências</Text>

      <Text style={estilos.secao}>APARÊNCIA</Text>
      <View style={estilos.grupo}>
        {OPCOES_TEMA.map((opcao, indice) => {
          const selecionado = modo === opcao.modo;
          const amostra = opcao.modo === "automatico" ? paletas[modoEfetivo] : paletas[opcao.modo];
          return (
            <Pressable
              key={opcao.modo}
              accessibilityRole="radio"
              accessibilityState={{ selected: selecionado }}
              accessibilityLabel={`${opcao.titulo} — ${opcao.descricao}`}
              android_ripple={{ color: cores.overlay }}
              onPress={() => definirModo(opcao.modo)}
              style={({ pressed }) => [
                estilos.opcao,
                indice > 0 && estilos.opcaoSeparada,
                pressed && estilos.opcaoPressionada,
              ]}
            >
              <View style={[estilos.radio, selecionado && estilos.radioAtivo]}>
                {selecionado ? <View style={estilos.radioMiolo} /> : null}
              </View>

              <View style={estilos.opcaoInfo}>
                <Text style={estilos.opcaoTitulo}>{opcao.titulo}</Text>
                <Text style={estilos.opcaoDescricao}>{opcao.descricao}</Text>
              </View>

              {/* Amostra da paleta que a opção aplica — escolher no escuro é o
                  que esta tela existe para evitar. */}
              <View style={[estilos.amostra, { backgroundColor: amostra.papel, borderColor: amostra.linha2 }]}>
                <View style={[estilos.amostraLinha, { backgroundColor: amostra.tinta }]} />
                <View style={[estilos.amostraLinha, estilos.amostraCurta, { backgroundColor: amostra.esmaecido }]} />
                <View style={[estilos.amostraBotao, { backgroundColor: amostra.marca }]} />
              </View>
            </Pressable>
          );
        })}
      </View>

      <Text style={estilos.secao}>SOM DE CONFIRMAÇÃO</Text>
      <View style={estilos.grupo}>
        <View style={estilos.opcao}>
          <View style={estilos.opcaoInfo}>
            <Text style={estilos.opcaoTitulo}>Avisar por som</Text>
            <Text style={estilos.opcaoDescricao}>
              Um som curto a cada comando aceito, recusado ou desfeito — para não precisar olhar a tela. Abaixa o
              volume da música por um instante, sem pausar.
            </Text>
          </View>
          <Switch
            value={som}
            onValueChange={alternarSom}
            accessibilityLabel="Avisar por som"
            trackColor={{ true: cores.marca, false: cores.linha2 }}
            thumbColor={cores.cartao}
          />
        </View>
      </View>
      <Text style={estilos.nota}>
        A vibração continua ligada nos dois casos — ela é o aviso que funciona com o telefone na mão, o som é o que
        funciona com ele no suporte do painel.
      </Text>

      <View style={estilos.rodape}>
        <Botao56 titulo="Voltar" variante="secundario" onPress={() => navigation.goBack()} />
        <Botao56 titulo="Sair da conta" variante="perigo" onPress={() => void logout()} />
      </View>
    </ScrollView>
  );
}

const criarEstilos = (cores: Paleta) =>
  StyleSheet.create({
    tela: {
      flex: 1,
      backgroundColor: cores.papel,
    },
    conteudo: {
      paddingHorizontal: espacamento.lg,
    },
    titulo: {
      fontSize: tipografia.destaque,
      fontWeight: peso.forte,
      color: cores.tinta,
    },
    secao: {
      fontSize: tipografia.legenda,
      fontWeight: peso.forte,
      letterSpacing: ESPACO_LETRA_SELO,
      color: cores.dica,
      marginTop: espacamento.xl,
      marginBottom: espacamento.sm,
    },
    grupo: {
      backgroundColor: cores.cartao,
      borderRadius: raio.md,
      borderWidth: 1,
      borderColor: cores.linha,
      overflow: "hidden",
    },
    opcao: {
      flexDirection: "row",
      alignItems: "center",
      gap: espacamento.md,
      minHeight: TOQUE_MIN + espacamento.md,
      paddingVertical: espacamento.md,
      paddingHorizontal: espacamento.md,
    },
    opcaoSeparada: {
      borderTopWidth: 1,
      borderTopColor: cores.linha,
    },
    opcaoPressionada: {
      opacity: 0.85,
    },
    radio: {
      width: 22,
      height: 22,
      borderRadius: raio.pilula,
      borderWidth: 2,
      borderColor: cores.bordaAcao,
      alignItems: "center",
      justifyContent: "center",
    },
    radioAtivo: {
      borderColor: cores.marca,
    },
    radioMiolo: {
      width: 11,
      height: 11,
      borderRadius: raio.pilula,
      backgroundColor: cores.marca,
    },
    opcaoInfo: {
      flex: 1,
    },
    opcaoTitulo: {
      fontSize: tipografia.corpo,
      fontWeight: peso.forte,
      color: cores.tinta,
    },
    opcaoDescricao: {
      fontSize: tipografia.legenda,
      color: cores.esmaecido,
      marginTop: 2,
      lineHeight: tipografia.legenda * 1.35,
    },
    amostra: {
      width: 52,
      height: 44,
      borderRadius: raio.sm,
      borderWidth: 1,
      padding: 6,
      gap: 4,
      justifyContent: "center",
    },
    amostraLinha: {
      height: 3,
      borderRadius: raio.pilula,
    },
    amostraCurta: {
      width: "60%",
    },
    amostraBotao: {
      height: 8,
      borderRadius: 3,
      marginTop: 2,
    },
    nota: {
      fontSize: tipografia.legenda,
      color: cores.dica,
      marginTop: espacamento.sm,
      lineHeight: tipografia.legenda * 1.35,
    },
    rodape: {
      marginTop: espacamento.xxl,
      gap: espacamento.md,
    },
  });
