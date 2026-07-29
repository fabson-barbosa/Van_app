/**
 * Diálogo de confirmação — anatomia do CLAUDE.md §6, generalizada (Bloco B7).
 *
 * Até o B5 o único diálogo bloqueante era o do "Cheguei". O B7 estendeu a
 * confirmação para as ações IRREVERSÍVEIS: `ausente` e `entregue` são estados
 * terminais na máquina de estados (não existe `desfazer_ausente` nem
 * `desfazer_checkout`) e `eventos_aluno` é append-only por trigger de banco
 * (§7.4) — um Ausente errado não tem correção nem por suporte. Como não há
 * "depois", a proteção precisa vir antes.
 *
 * Conteúdo taxativo, herdado do §6: título em destaque, subtítulo de peso leve
 * em cor secundária, dois botões, NADA MAIS. Nenhum diálogo do app pode ganhar
 * checkbox, terceira opção ou texto explicativo extra — o motorista está
 * dirigindo, e o custo de ler é o que se está tentando eliminar.
 *
 * GUARDA_MS existe porque o risco real não é o toque acidental, é o REFLEXO:
 * um diálogo que sempre aparece no mesmo lugar vira "toca duas vezes" em três
 * dias, e aí ele deixou de proteger. Travar os botões por um instante depois
 * de abrir garante que o segundo toque de um toque-duplo não confirme nada.
 */
import React, { useEffect, useState } from "react";
import { Modal, StyleSheet, Text, View } from "react-native";

import { Botao56 } from "./Botao56";
import { cores, espacamento, raio, tipografia } from "../theme";

/** Janela em que os botões ficam inertes depois de o diálogo abrir. */
export const GUARDA_MS = 400;

interface Props {
  visivel: boolean;
  titulo: string;
  subtitulo?: string | null;
  rotuloConfirmar?: string;
  varianteConfirmar?: "primario" | "destrutivo";
  onConfirmar: () => void;
  onCancelar: () => void;
}

export function DialogoConfirmacao({
  visivel,
  titulo,
  subtitulo,
  rotuloConfirmar = "Confirmar",
  varianteConfirmar = "primario",
  onConfirmar,
  onCancelar,
}: Props): React.JSX.Element {
  const [liberado, setLiberado] = useState(false);

  useEffect(() => {
    if (!visivel) {
      setLiberado(false);
      return undefined;
    }
    const timer = setTimeout(() => setLiberado(true), GUARDA_MS);
    return () => clearTimeout(timer);
  }, [visivel]);

  return (
    <Modal
      visible={visivel}
      transparent
      animationType="fade"
      // Botão físico Voltar do Android CANCELA — nunca confirma.
      onRequestClose={onCancelar}
    >
      <View style={estilos.fundo}>
        <View style={estilos.cartao}>
          <Text style={estilos.titulo}>{titulo}</Text>
          {subtitulo ? <Text style={estilos.subtitulo}>{subtitulo}</Text> : null}

          <View style={estilos.botoes}>
            <Botao56
              titulo="Cancelar"
              variante="secundario"
              tamanho="grande"
              desabilitado={!liberado}
              onPress={onCancelar}
              estilo={estilos.botao}
              testID="dialogo-cancelar"
            />
            <Botao56
              titulo={rotuloConfirmar}
              variante={varianteConfirmar}
              tamanho="grande"
              desabilitado={!liberado}
              onPress={onConfirmar}
              estilo={estilos.botao}
              testID="dialogo-confirmar"
            />
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
  titulo: {
    fontSize: tipografia.destaque,
    fontWeight: "700",
    color: cores.tinta,
    textAlign: "center",
  },
  subtitulo: {
    fontSize: tipografia.legenda,
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
