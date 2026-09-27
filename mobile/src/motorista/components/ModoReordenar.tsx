/**
 * Barra de ação do modo de reordenação (CLAUDE.md §8 — só alunos ainda em
 * 'aguardando'; as setas por linha estão em `AlunoRow.tsx`). Reordenar é
 * online-only (ver `shared/offline/queue.ts`) — "Concluir ordem" chama a API
 * direto; sem sinal, o erro aparece inline e o motorista tenta de novo ou
 * cancela.
 *
 * Bloco B8: a barra ganhou fundo e título. Ela SUBSTITUI o card de parada atual
 * enquanto o modo está ligado, e sem nenhuma moldura a tela dava a impressão de
 * ter perdido a ação primária — o motorista não tinha como saber em que modo
 * estava, só que o botão grande havia desaparecido.
 */
import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Botao56 } from "../../shared/components/Botao56";
import {
  ESPACO_LETRA_SELO,
  type Paleta,
  espacamento,
  peso,
  raio,
  tipografia,
  useEstilos,
  useTema,
} from "../../shared/theme";

interface Props {
  onConcluir: () => void;
  onCancelar: () => void;
  salvando: boolean;
}

export function ModoReordenar({ onConcluir, onCancelar, salvando }: Props): React.JSX.Element {
  const { cores } = useTema();
  const estilos = useEstilos(criarEstilos, cores);
  const insets = useSafeAreaInsets();

  return (
    <View style={[estilos.base, { paddingBottom: espacamento.lg + insets.bottom }]}>
      <Text style={estilos.secao}>REORDENANDO PARADAS</Text>
      <Text style={estilos.dica}>Use as setas nas linhas. Só quem ainda não embarcou pode mudar de lugar.</Text>

      <View style={estilos.botoes}>
        <Botao56
          titulo="Cancelar"
          variante="secundario"
          onPress={onCancelar}
          desabilitado={salvando}
          estilo={estilos.botao}
        />
        <Botao56
          titulo="Salvar ordem"
          variante="primario"
          onPress={onConcluir}
          carregando={salvando}
          estilo={estilos.botao}
        />
      </View>
    </View>
  );
}

const criarEstilos = (cores: Paleta) =>
  StyleSheet.create({
    base: {
      backgroundColor: cores.cartao,
      borderTopWidth: 1,
      borderTopColor: cores.linha2,
      borderTopLeftRadius: raio.lg,
      borderTopRightRadius: raio.lg,
      paddingHorizontal: espacamento.lg,
      paddingTop: espacamento.md,
    },
    secao: {
      fontSize: tipografia.legenda,
      fontWeight: peso.forte,
      letterSpacing: ESPACO_LETRA_SELO,
      color: cores.info,
    },
    dica: {
      fontSize: tipografia.endereco,
      color: cores.esmaecido,
      marginTop: espacamento.xs,
    },
    botoes: {
      flexDirection: "row",
      gap: espacamento.md,
      marginTop: espacamento.lg,
    },
    botao: {
      flex: 1,
    },
  });
