/**
 * Indicador persistente de conectividade + itens pendentes — requisito explícito
 * do offline-first (CLAUDE.md §8: deixar visível o que ainda não sincronizou).
 *
 * Bloco B8: era uma faixa de largura total com 12sp (abaixo do piso de 13sp) e
 * fundo tingido que competia com os banners de erro logo abaixo. Virou de fato
 * uma pílula — centrada, compacta, com um ponto de status colorido. Ocupa menos
 * altura vertical na tela mais densa do app e deixa de parecer um alerta, que é
 * o que ela nunca foi: "3 pendentes" é informação de rotina numa rota com sinal
 * ruim, não um problema.
 */
import NetInfo from "@react-native-community/netinfo";
import React, { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { assinar } from "../offline/sync";
import * as fila from "../offline/queue";
import { type Paleta, espacamento, peso, raio, tipografia, useEstilos, useTema } from "../theme";

export function PillSync(): React.JSX.Element | null {
  const { cores } = useTema();
  const estilos = useEstilos(criarEstilos, cores);
  const [online, setOnline] = useState(true);
  const [pendentes, setPendentes] = useState(0);

  useEffect(() => {
    const cancelarNetInfo = NetInfo.addEventListener((estado) => setOnline(estado.isConnected ?? true));

    fila.tamanho().then(setPendentes).catch(() => undefined);
    const cancelarSync = assinar((evento) => {
      if (evento.tipo === "fila_mudou") setPendentes(evento.quantidade);
    });

    return () => {
      cancelarNetInfo();
      cancelarSync();
    };
  }, []);

  if (online && pendentes === 0) return null;

  const plural = pendentes > 1 ? "s" : "";
  const texto = !online
    ? pendentes > 0
      ? `Sem conexão · ${pendentes} na fila`
      : "Sem conexão"
    : `Sincronizando · ${pendentes} item${plural}`;

  return (
    <View style={estilos.faixa}>
      <View style={[estilos.pilula, !online ? estilos.offline : estilos.sincronizando]}>
        <View style={[estilos.ponto, { backgroundColor: online ? cores.ambar : cores.perigo }]} />
        <Text style={[estilos.texto, { color: online ? cores.ambar : cores.perigo }]} numberOfLines={1}>
          {texto}
        </Text>
      </View>
    </View>
  );
}

const criarEstilos = (cores: Paleta) =>
  StyleSheet.create({
    faixa: {
      alignItems: "center",
      paddingTop: espacamento.xs,
      paddingBottom: espacamento.xs,
    },
    pilula: {
      flexDirection: "row",
      alignItems: "center",
      gap: espacamento.sm,
      paddingVertical: 5,
      paddingHorizontal: espacamento.md,
      borderRadius: raio.pilula,
      borderWidth: 1,
    },
    offline: {
      backgroundColor: cores.perigoSuave,
      borderColor: cores.perigoBorda,
    },
    sincronizando: {
      backgroundColor: cores.ambarSuave,
      borderColor: cores.ambarBorda,
    },
    ponto: {
      width: 7,
      height: 7,
      borderRadius: raio.pilula,
    },
    texto: {
      fontSize: tipografia.legenda,
      fontWeight: peso.forte,
    },
  });
