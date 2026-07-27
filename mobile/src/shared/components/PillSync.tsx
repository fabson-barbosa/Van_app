/**
 * Indicador persistente de conectividade + itens pendentes — requisito
 * explícito do offline-first (CLAUDE.md §8): "a UI... deve deixar visível o
 * que ainda não sincronizou".
 */
import NetInfo from "@react-native-community/netinfo";
import React, { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { assinar } from "../offline/sync";
import * as fila from "../offline/queue";
import { cores } from "../theme";

export function PillSync(): React.JSX.Element | null {
  const [online, setOnline] = useState(true);
  const [pendentes, setPendentes] = useState(0);

  useEffect(() => {
    const cancelarNetInfo = NetInfo.addEventListener((estado) => setOnline(estado.isConnected ?? true));

    fila.tamanho().then(setPendentes);
    const cancelarSync = assinar((evento) => {
      if (evento.tipo === "fila_mudou") setPendentes(evento.quantidade);
    });

    return () => {
      cancelarNetInfo();
      cancelarSync();
    };
  }, []);

  if (online && pendentes === 0) return null;

  const texto = !online
    ? pendentes > 0
      ? `Sem conexão · ${pendentes} pendente${pendentes > 1 ? "s" : ""}`
      : "Sem conexão"
    : `Sincronizando · ${pendentes} pendente${pendentes > 1 ? "s" : ""}`;

  return (
    <View style={[estilos.base, !online ? estilos.offline : estilos.sincronizando]}>
      <Text style={estilos.texto}>{texto}</Text>
    </View>
  );
}

const estilos = StyleSheet.create({
  base: {
    paddingVertical: 6,
    paddingHorizontal: 14,
    alignItems: "center",
  },
  offline: {
    backgroundColor: cores.perigoSuave,
  },
  sincronizando: {
    backgroundColor: cores.ambarSuave,
  },
  texto: {
    fontSize: 12,
    fontWeight: "700",
    color: cores.tinta,
  },
});
