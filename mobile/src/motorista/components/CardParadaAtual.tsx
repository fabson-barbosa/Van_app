/**
 * Card da parada atual — a única ação primária da tela (Bloco B7).
 *
 * Antes do B7 a `ViagemScreen` era uma lista uniforme de N alunos, todos com o
 * mesmo peso visual e um botão cada. O motorista tinha que LER a tela e ACHAR
 * qual linha era a dele — parado em fila dupla, com a van ligada. Numa rota de
 * doze alunos, depois de oito entregues o alvo já estava fora da tela.
 *
 * Aqui a ação vem até ele: fica no rodapé (zona do polegar, não no topo), ocupa a
 * largura toda, tem 72dp de altura e nunca sai da tela. A lista acima virou
 * consulta. Efeito colateral bem-vindo: como o alvo não rola, não é preciso
 * `scrollToIndex` — um mecanismo a menos para falhar.
 *
 * O selo fica tocável aqui pelo mesmo motivo que fica na lista: é o canal das
 * ações fora de ordem (§4 — desfazer chegada, marcar ausente), e tê-lo no card
 * evita caçar a linha do aluno para corrigir a parada em que se está parado.
 *
 * Bloco B8 — o card passou a ser o elemento mais forte da tela, não só o mais
 * baixo:
 *
 * - **Rótulo de seção** ("PARADA ATUAL" / "DESEMBARQUE"), porque um card sem
 *   título, colado no rodapé, é lido como barra de navegação.
 * - **O nome cresceu e o número saiu da frente dele.** A ordem virou um disco à
 *   esquerda: continua disponível para casar com a sequência, sem disputar a
 *   primeira fixação do olho com o nome — que é o dado do §6, o que evita
 *   registrar Cheguei na parada errada.
 * - **O tempo de espera virou o dado dominante quando ele existe.** Parado na
 *   porta, "esperando há 2min14" é a informação que decide se o motorista toca
 *   Checkin ou marca ausente; antes era uma legenda cinza de 14sp.
 * - **A ação primária carrega o endereço como segunda linha** quando está em
 *   `aguardando`: o alvo de 72dp que ele vai tocar mostra para onde está indo.
 */
import React, { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Botao56 } from "../../shared/components/Botao56";
import { EstadoBadge } from "../../shared/components/EstadoBadge";
import type { TripStudentOut } from "../../shared/api/types";
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
import { formatarEspera, type FaseViagem } from "../state/paradaAtual";
import { temAcoesForaDeOrdem } from "./MenuAcoesAluno";

const ROTULO_ACAO: Record<string, string> = {
  aguardando: "Cheguei",
  chegou: "Checkin",
  a_bordo: "Checkout",
};

interface Props {
  alvo: TripStudentOut;
  fase: FaseViagem;
  pendente: boolean;
  onAcaoPrimaria: () => void;
  onAbrirAcoes: () => void;
}

export function CardParadaAtual({
  alvo,
  fase,
  pendente,
  onAcaoPrimaria,
  onAbrirAcoes,
}: Props): React.JSX.Element {
  const { cores } = useTema();
  const estilos = useEstilos(criarEstilos, cores);
  const insets = useSafeAreaInsets();
  const [agoraMs, setAgoraMs] = useState(() => Date.now());

  // Cronômetro só corre enquanto o motorista está de fato esperando na porta.
  useEffect(() => {
    if (alvo.estado !== "chegou" || !alvo.chegou_em) return undefined;
    const intervalo = setInterval(() => setAgoraMs(Date.now()), 1000);
    return () => clearInterval(intervalo);
  }, [alvo.estado, alvo.chegou_em]);

  const esperando = alvo.estado === "chegou" && alvo.chegou_em != null;

  // No desembarque o endereço da parada é o ponto de EMBARQUE (snapshot da
  // origem — ver docstring de models/trip_student.py). Mostrá-lo enquanto a van
  // descarrega na escola apontaria o motorista para o lugar errado.
  const endereco = fase === "desembarque" ? null : alvo.parada_endereco;

  return (
    <View style={[estilos.base, { paddingBottom: espacamento.lg + insets.bottom }]}>
      <Text style={estilos.secao}>{fase === "desembarque" ? "DESEMBARQUE" : "PARADA ATUAL"}</Text>

      <View style={estilos.topo}>
        <View style={estilos.disco}>
          <Text style={estilos.discoTexto}>{alvo.ordem}</Text>
        </View>

        <View style={estilos.info}>
          <Text style={estilos.nome} numberOfLines={1}>
            {alvo.aluno_nome}
          </Text>
          {endereco ? (
            <Text style={estilos.endereco} numberOfLines={1}>
              {endereco}
            </Text>
          ) : null}
        </View>

        <EstadoBadge
          estado={alvo.estado}
          nomeAluno={alvo.aluno_nome}
          onPress={temAcoesForaDeOrdem(alvo.estado) ? onAbrirAcoes : undefined}
        />
      </View>

      {esperando && alvo.chegou_em ? (
        <View style={estilos.espera}>
          <Text style={estilos.esperaTexto}>{formatarEspera(alvo.chegou_em, agoraMs)}</Text>
        </View>
      ) : null}

      {pendente ? <Text style={estilos.pendente}>na fila — ainda não sincronizado</Text> : null}

      <Botao56
        titulo={ROTULO_ACAO[alvo.estado] ?? "Aguarde"}
        // O endereço repetido dentro do botão é intencional só no `aguardando`:
        // é o único estado em que a ação move a van para outro lugar.
        detalhe={alvo.estado === "aguardando" ? endereco : null}
        tamanho="grande"
        onPress={onAcaoPrimaria}
        estilo={estilos.acao}
        testID="acao-primaria"
        accessibilityLabel={`${ROTULO_ACAO[alvo.estado] ?? "Aguarde"} — ${alvo.aluno_nome}`}
      />
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
      color: cores.dica,
      marginBottom: espacamento.sm,
    },
    topo: {
      flexDirection: "row",
      alignItems: "center",
      gap: espacamento.md,
    },
    disco: {
      width: 44,
      height: 44,
      borderRadius: raio.pilula,
      backgroundColor: cores.marcaSuave,
      borderWidth: 1,
      borderColor: cores.marcaBorda,
      alignItems: "center",
      justifyContent: "center",
    },
    discoTexto: {
      fontSize: tipografia.titulo,
      fontWeight: peso.forte,
      color: cores.marca,
    },
    info: {
      flex: 1,
    },
    nome: {
      fontSize: tipografia.destaque,
      fontWeight: peso.forte,
      color: cores.tinta,
    },
    endereco: {
      fontSize: tipografia.endereco,
      color: cores.esmaecido,
      marginTop: 2,
    },
    espera: {
      marginTop: espacamento.md,
      alignSelf: "flex-start",
      backgroundColor: cores.infoSuave,
      borderWidth: 1,
      borderColor: cores.infoBorda,
      borderRadius: raio.pilula,
      paddingVertical: 6,
      paddingHorizontal: espacamento.md,
    },
    esperaTexto: {
      fontSize: tipografia.subtitulo,
      fontWeight: peso.forte,
      color: cores.info,
    },
    pendente: {
      fontSize: tipografia.legenda,
      color: cores.ambar,
      fontWeight: peso.forte,
      marginTop: espacamento.sm,
    },
    acao: {
      marginTop: espacamento.lg,
    },
  });
