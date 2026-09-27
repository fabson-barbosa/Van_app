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
 * GUARDA_MS existe porque o risco real não é o toque acidental, é o REFLEXO: um
 * diálogo que sempre aparece no mesmo lugar vira "toca duas vezes" em três dias,
 * e aí ele deixou de proteger. Travar os botões por um instante depois de abrir
 * garante que o segundo toque de um toque-duplo não confirme nada.
 *
 * Bloco B8 — o desenho mudou, o contrato não:
 *
 * - **Confirmar em cima, Cancelar embaixo**, em coluna. Lado a lado, os dois
 *   botões tinham a mesma massa visual e ficavam a 12dp um do outro: ruim para
 *   um alvo que é irreversível e outro que é a saída. Em coluna o confirmar
 *   ocupa a largura toda na zona do polegar e o cancelar fica claramente
 *   separado dele.
 * - **A guarda agora é visível.** Botão travado por 400ms sem explicação parece
 *   travamento do app; o subtítulo do botão mostra a contagem. Sem isso o
 *   motorista toca de novo achando que não pegou — exatamente o reflexo que a
 *   guarda existe para impedir.
 */
import React, { useEffect, useState } from "react";
import { Modal, StyleSheet, Text, View } from "react-native";

import { Botao56 } from "./Botao56";
import { type Paleta, espacamento, peso, raio, tipografia, useEstilos, useTema } from "../theme";

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
  const { cores } = useTema();
  const estilos = useEstilos(criarEstilos, cores);
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
      statusBarTranslucent
      // Botão físico Voltar do Android CANCELA — nunca confirma.
      onRequestClose={onCancelar}
    >
      <View style={estilos.fundo}>
        <View style={estilos.cartao}>
          <Text style={estilos.titulo}>{titulo}</Text>
          {subtitulo ? <Text style={estilos.subtitulo}>{subtitulo}</Text> : null}

          <View style={estilos.botoes}>
            <Botao56
              titulo={rotuloConfirmar}
              variante={varianteConfirmar}
              tamanho="grande"
              desabilitado={!liberado}
              detalhe={liberado ? null : "aguarde um instante"}
              onPress={onConfirmar}
              testID="dialogo-confirmar"
            />
            <Botao56
              titulo="Cancelar"
              variante="secundario"
              tamanho="grande"
              desabilitado={!liberado}
              onPress={onCancelar}
              testID="dialogo-cancelar"
            />
          </View>
        </View>
      </View>
    </Modal>
  );
}

const criarEstilos = (cores: Paleta) =>
  StyleSheet.create({
    fundo: {
      flex: 1,
      backgroundColor: cores.overlay,
      alignItems: "center",
      justifyContent: "center",
      padding: espacamento.xl,
    },
    cartao: {
      width: "100%",
      maxWidth: 400,
      backgroundColor: cores.cartao,
      borderRadius: raio.lg,
      borderWidth: 1,
      borderColor: cores.linha2,
      paddingVertical: espacamento.xl,
      paddingHorizontal: espacamento.lg,
    },
    titulo: {
      fontSize: tipografia.destaque,
      fontWeight: peso.forte,
      color: cores.tinta,
      textAlign: "center",
    },
    subtitulo: {
      fontSize: tipografia.endereco,
      fontWeight: peso.normal,
      color: cores.esmaecido,
      textAlign: "center",
      marginTop: espacamento.sm,
      lineHeight: tipografia.endereco * 1.4,
    },
    botoes: {
      gap: espacamento.md,
      marginTop: espacamento.xl,
    },
  });
