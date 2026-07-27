/**
 * Único diálogo bloqueante do app (CLAUDE.md §6). Conteúdo taxativo:
 * nome do aluno em destaque, endereço abaixo (peso leve, cor secundária,
 * ~13sp), dois botões — Confirmar/Cancelar, nada mais.
 */
import React from "react";
import { Modal, StyleSheet, Text, View } from "react-native";

import { Botao56 } from "../../shared/components/Botao56";
import { cores, espacamento, raio } from "../../shared/theme";

interface Props {
  visivel: boolean;
  nomeAluno: string;
  endereco: string | null;
  onConfirmar: () => void;
  onCancelar: () => void;
}

export function DialogoCheguei({ visivel, nomeAluno, endereco, onConfirmar, onCancelar }: Props): React.JSX.Element {
  return (
    <Modal visible={visivel} transparent animationType="fade" onRequestClose={onCancelar}>
      <View style={estilos.fundo}>
        <View style={estilos.cartao}>
          <Text style={estilos.nome}>{nomeAluno}</Text>
          {endereco ? <Text style={estilos.endereco}>{endereco}</Text> : null}

          <View style={estilos.botoes}>
            <Botao56 titulo="Cancelar" variante="secundario" onPress={onCancelar} estilo={estilos.botao} />
            <Botao56 titulo="Confirmar" variante="primario" onPress={onConfirmar} estilo={estilos.botao} />
          </View>
        </View>
      </View>
    </Modal>
  );
}

const estilos = StyleSheet.create({
  fundo: {
    flex: 1,
    backgroundColor: "rgba(16,35,30,0.55)",
    alignItems: "center",
    justifyContent: "center",
    padding: espacamento.xl,
  },
  cartao: {
    width: "100%",
    maxWidth: 380,
    backgroundColor: cores.cartao,
    borderRadius: raio.lg,
    padding: espacamento.xl,
  },
  nome: {
    fontSize: 22,
    fontWeight: "700",
    color: cores.tinta,
    textAlign: "center",
  },
  endereco: {
    fontSize: 13,
    fontWeight: "400",
    color: cores.esmaecido,
    textAlign: "center",
    marginTop: espacamento.xs,
  },
  botoes: {
    flexDirection: "row",
    gap: espacamento.md,
    marginTop: espacamento.xl,
  },
  botao: {
    flex: 1,
  },
});
