/**
 * Undo de 30s do Checkin (CLAUDE.md §8) — a janela do SERVIDOR é 60s (tolerância
 * a latência/fila offline), mas a UI só oferece 30s para não incentivar o
 * motorista a "corrigir" depois de a van já ter saído do lugar.
 *
 * Bloco B7: o prazo vem de `expiraEm` (instante absoluto, guardado em
 * `state/undoCheckin.ts`), não de um contador interno. Remontar o componente —
 * voltar de outra tela, o Android recriar a view — não devolve tempo que já
 * passou.
 *
 * Bloco B8 — duas mudanças:
 *
 * - **A contagem virou uma barra que vaza.** O número "30s... 29s..." exige ler;
 *   uma barra encurtando é apreensível pela visão periférica, que é a única
 *   disponível para quem está dirigindo. O número fica, pequeno, para quem quiser
 *   conferir.
 * - **`inverso`, não `tinta`.** A barra era `backgroundColor: cores.tinta` com
 *   texto branco fixo — no tema escuro `tinta` É quase branco, então a barra
 *   ficaria branca com texto branco. `inverso`/`sobreInverso` existem para isso,
 *   e no escuro a barra é uma superfície elevada em vez de invertida: uma faixa
 *   branca no painel, de noite, ofusca.
 */
import React, { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import {
  TOQUE_MIN,
  type Paleta,
  espacamento,
  peso,
  raio,
  tipografia,
  useEstilos,
  useTema,
} from "../../shared/theme";

/** Janela oferecida na UI. O servidor aceita 60s; ver docstring acima. */
const JANELA_MS = 30_000;

interface Props {
  nomeAluno: string;
  /** Instante absoluto (ms) em que a oferta expira. */
  expiraEm: number;
  onDesfazer: () => void;
  onExpirar: () => void;
}

function segundosRestantes(expiraEm: number): number {
  return Math.max(0, Math.ceil((expiraEm - Date.now()) / 1000));
}

export function BarraUndo({ nomeAluno, expiraEm, onDesfazer, onExpirar }: Props): React.JSX.Element {
  const { cores } = useTema();
  const estilos = useEstilos(criarEstilos, cores);
  const [restante, setRestante] = useState(() => segundosRestantes(expiraEm));

  useEffect(() => {
    const intervalo = setInterval(() => {
      const agora = segundosRestantes(expiraEm);
      setRestante(agora);
      if (agora <= 0) {
        clearInterval(intervalo);
        onExpirar();
      }
    }, 1000);
    return () => clearInterval(intervalo);
    // `onExpirar` é recriado a cada render da tela; incluí-lo reiniciaria o
    // intervalo o tempo todo. `expiraEm` é a identidade real desta barra.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expiraEm]);

  const fracao = Math.max(0, Math.min(1, (restante * 1000) / JANELA_MS));

  return (
    <View style={estilos.base}>
      <View style={estilos.corpo}>
        <View style={estilos.info}>
          <Text style={estilos.titulo} numberOfLines={1}>
            Checkin de {nomeAluno}
          </Text>
          <Text style={estilos.prazo}>{restante}s para desfazer</Text>
        </View>

        <Pressable
          accessibilityRole="button"
          accessibilityLabel={`Desfazer checkin de ${nomeAluno}`}
          onPress={onDesfazer}
          android_ripple={{ color: cores.overlay }}
          style={({ pressed }) => [estilos.botao, pressed && estilos.botaoPressionado]}
          hitSlop={8}
        >
          <Text style={estilos.botaoTexto}>DESFAZER</Text>
        </Pressable>
      </View>

      {/* Progresso vazando da direita para a esquerda: o tempo "sai" da barra. */}
      <View style={estilos.trilha}>
        <View style={[estilos.preenchimento, { width: `${fracao * 100}%` }]} />
      </View>
    </View>
  );
}

const criarEstilos = (cores: Paleta) =>
  StyleSheet.create({
    base: {
      backgroundColor: cores.inverso,
      borderRadius: raio.md,
      marginBottom: espacamento.sm,
      overflow: "hidden",
    },
    corpo: {
      flexDirection: "row",
      alignItems: "center",
      paddingLeft: espacamento.lg,
      paddingRight: espacamento.xs,
    },
    info: {
      flex: 1,
      paddingVertical: espacamento.sm,
    },
    titulo: {
      color: cores.sobreInverso,
      fontSize: tipografia.endereco,
      fontWeight: peso.forte,
    },
    prazo: {
      color: cores.sobreInverso,
      fontSize: tipografia.legenda,
      opacity: 0.75,
      marginTop: 1,
    },
    botao: {
      minWidth: 108,
      minHeight: TOQUE_MIN,
      alignItems: "center",
      justifyContent: "center",
      paddingHorizontal: espacamento.md,
      borderRadius: raio.sm,
      overflow: "hidden",
    },
    botaoPressionado: {
      opacity: 0.7,
    },
    botaoTexto: {
      color: cores.destaqueInverso,
      fontSize: tipografia.endereco,
      fontWeight: peso.forte,
      letterSpacing: 0.5,
    },
    trilha: {
      height: 3,
      backgroundColor: "transparent",
    },
    preenchimento: {
      height: 3,
      backgroundColor: cores.destaqueInverso,
    },
  });
