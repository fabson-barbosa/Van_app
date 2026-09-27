/**
 * Tela 3 — Viagem em andamento.
 *
 * Bloco B7 reestruturou a tela. A lista deixou de ser onde o motorista AGE e
 * virou onde ele CONSULTA: a ação primária mora no card fixo do rodapé
 * (`CardParadaAtual`), na zona do polegar, e nunca sai da tela. As correções fora
 * de ordem entram pelo selo de cada linha (`MenuAcoesAluno`).
 *
 * `useKeepAwake` fica só aqui, não no app inteiro: com viagem em andamento e o
 * aparelho no painel da van, manter a tela acesa se justifica — o motorista
 * destravava o telefone a cada casa. Fora desta tela seria só bateria.
 *
 * Bloco B8 — a tela tinha oito elementos empilhados entre o cabeçalho e a lista
 * (três banners, painel de atraso, confirmação, erro de reordenar...), todos
 * podendo aparecer ao mesmo tempo e empurrar a lista para fora da tela:
 *
 * - **Progresso no cabeçalho.** Uma barra de paradas resolvidas responde "onde eu
 *   estou na rota" sem ler número nenhum. Antes só existia o texto "4 alunos
 *   restantes", e o dado de atraso — que o B3 calcula desde sempre — vinha
 *   concatenado nele com um "·".
 * - **Os banners viraram um componente** (`Banner`) e no máximo um bloqueante
 *   aparece por vez: bloqueio do §7.2 e conflito da fila são a mesma classe de
 *   problema, e mostrar os dois juntos só empurra a lista para baixo.
 * - **"Estou atrasado" saiu do rodapé para o cabeçalho**, junto do dado de atraso
 *   que ele altera. Estava a 8dp de "Reordenar paradas", colado no card da ação
 *   primária — três alvos disputando a mesma faixa da tela.
 */
import React, { useCallback, useEffect, useMemo, useState } from "react";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { FlatList, Pressable, RefreshControl, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useKeepAwake } from "expo-keep-awake";

import { ApiError, NetworkError } from "../../shared/api/client";
import { endpoints } from "../../shared/api/endpoints";
import { Banner } from "../../shared/components/Banner";
import { Botao56 } from "../../shared/components/Botao56";
import { DialogoConfirmacao } from "../../shared/components/DialogoConfirmacao";
import { PillSync } from "../../shared/components/PillSync";
import { LinkToque } from "../../shared/components/LinkToque";
import { feedbackAceito, feedbackConcluido, feedbackDesfeito, feedbackErro } from "../../shared/feedback";
import {
  ESPACO_LETRA_SELO,
  TOQUE_MIN,
  type Paleta,
  espacamento,
  peso,
  raio,
  tipografia,
  useEstilos,
  useTema,
} from "../../shared/theme";
import type { RootStackParamList } from "../../navigation/RootNavigator";
import { AlunoRow } from "../components/AlunoRow";
import { BarraUndo } from "../components/BarraUndo";
import { CardParadaAtual } from "../components/CardParadaAtual";
import { DialogoCheguei } from "../components/DialogoCheguei";
import { MenuAcoesAluno } from "../components/MenuAcoesAluno";
import { ModoReordenar } from "../components/ModoReordenar";
import { useViagemStore } from "../state/ViagemStore";
import { contarRestantes, ehTerminal, rotuloAtraso, selecionarParadaAtual } from "../state/paradaAtual";
import { useUndosCheckin } from "../state/useUndosCheckin";
import type { TripStudentOut } from "../../shared/api/types";

const OPCOES_ATRASO_MINUTOS = [5, 10, 15, 20];

type Props = NativeStackScreenProps<RootStackParamList, "Viagem">;

export function ViagemScreen({ route, navigation }: Props): React.JSX.Element {
  const { viagemId } = route.params;
  const { cores } = useTema();
  const estilos = useEstilos(criarEstilos, cores);
  const store = useViagemStore(viagemId);
  const undos = useUndosCheckin(viagemId);
  const insets = useSafeAreaInsets();
  useKeepAwake();

  const [dialogoCheguei, setDialogoCheguei] = useState<TripStudentOut | null>(null);
  const [dialogoAusente, setDialogoAusente] = useState<TripStudentOut | null>(null);
  const [dialogoCheckout, setDialogoCheckout] = useState<TripStudentOut | null>(null);
  const [menuAluno, setMenuAluno] = useState<TripStudentOut | null>(null);
  const [bloqueioParadaAnterior, setBloqueioParadaAnterior] = useState<string | null>(null);
  const [reordenando, setReordenando] = useState(false);
  const [ordemRascunho, setOrdemRascunho] = useState<TripStudentOut[]>([]);
  const [salvandoOrdem, setSalvandoOrdem] = useState(false);
  const [erroReordenar, setErroReordenar] = useState<string | null>(null);
  const [mostrarAtraso, setMostrarAtraso] = useState(false);
  const [enviandoAtrasoMinutos, setEnviandoAtrasoMinutos] = useState<number | null>(null);
  const [confirmacaoAtraso, setConfirmacaoAtraso] = useState<string | null>(null);
  const [erroAtraso, setErroAtraso] = useState<string | null>(null);

  const alunosAguardando = useMemo(
    () => store.tripStudents.filter((ts) => ts.estado === "aguardando"),
    [store.tripStudents]
  );

  const restantes = useMemo(() => contarRestantes(store.tripStudents), [store.tripStudents]);
  const resolvidos = store.tripStudents.length - restantes;
  const paradaAtual = useMemo(() => selecionarParadaAtual(store.tripStudents), [store.tripStudents]);
  const atraso = store.viagem ? rotuloAtraso(store.viagem.atraso_acumulado_segundos) : null;

  // Vibra e toca quando a fila devolve um 409 de domínio — o banner é visual, e o
  // motorista pode estar de olho na rua quando o conflito chega.
  useEffect(() => {
    if (store.conflito) feedbackErro();
  }, [store.conflito]);

  function solicitarCheguei(tripStudent: TripStudentOut) {
    // §7.2 (CLAUDE.md) — guard de UI espelhando o 409 ParadaAnteriorPendenteError.
    const pendentes = store.paradasAnterioresPendentes(tripStudent.id);
    if (pendentes.length > 0) {
      feedbackErro();
      const nomes = pendentes.map((p) => `${p.ordem}. ${p.aluno_nome}`).join(", ");
      // O banner CITA O CAMINHO: o §7.2 pede "forçar resolução na tela
      // imediatamente", e um alerta com um "Entendi" interrompia sem levar a
      // lugar nenhum.
      setBloqueioParadaAnterior(
        `Resolva ${nomes} antes. Toque no selo de estado dele para fazer o checkin, desfazer a chegada ou marcar ausente.`
      );
      return;
    }
    setDialogoCheguei(tripStudent);
  }

  async function confirmarCheguei() {
    if (!dialogoCheguei) return;
    const alvo = dialogoCheguei;
    setDialogoCheguei(null);
    feedbackAceito();
    await store.marcarCheguei(alvo.id);
  }

  async function confirmarAusente() {
    if (!dialogoAusente) return;
    const alvo = dialogoAusente;
    setDialogoAusente(null);
    feedbackConcluido();
    await store.marcarAusente(alvo.id);
  }

  async function confirmarCheckout() {
    if (!dialogoCheckout) return;
    const alvo = dialogoCheckout;
    setDialogoCheckout(null);
    feedbackConcluido();
    await store.marcarCheckout(alvo.id);
  }

  async function fazerCheckin(tripStudent: TripStudentOut) {
    feedbackAceito();
    // O undo é registrado pelo store (estado de módulo), não por esta tela — é o
    // que o mantém vivo ao navegar até "Finalizar viagem" e voltar.
    await store.marcarCheckin(tripStudent.id, tripStudent.aluno_nome);
  }

  /** Ação primária do card — o rótulo e o efeito seguem o estado do alvo. */
  function acaoPrimaria(alvo: TripStudentOut) {
    if (alvo.estado === "aguardando") return solicitarCheguei(alvo);
    if (alvo.estado === "chegou") return void fazerCheckin(alvo);
    if (alvo.estado === "a_bordo") return setDialogoCheckout(alvo);
    return undefined;
  }

  function desfazerChegadaDoMenu() {
    if (!menuAluno) return;
    const alvo = menuAluno;
    setMenuAluno(null);
    feedbackDesfeito();
    void store.desfazerChegada(alvo.id);
  }

  function pedirAusenteDoMenu() {
    if (!menuAluno) return;
    const alvo = menuAluno;
    setMenuAluno(null);
    setDialogoAusente(alvo);
  }

  function desfazerCheckin(tripStudentId: string, eventId: string) {
    feedbackDesfeito();
    void store.desfazerCheckin(tripStudentId, eventId);
  }

  /** "Estou atrasado" (CLAUDE.md §5) — empurra a cauda manualmente e reagenda os
   * avisos pendentes. Online-only (mesmo padrão de reordenar/iniciar/finalizar —
   * ação de fronteira, rara, precisa da resposta do servidor para fazer sentido),
   * então não passa pela fila offline. */
  async function marcarAtraso(minutos: number) {
    setEnviandoAtrasoMinutos(minutos);
    setErroAtraso(null);
    try {
      await endpoints.estouAtrasado(viagemId, { minutos });
      feedbackAceito();
      setConfirmacaoAtraso(`Avisamos os responsáveis pendentes: +${minutos} min na rota.`);
      setMostrarAtraso(false);
      void store.recarregar();
    } catch (e) {
      feedbackErro();
      setErroAtraso(
        e instanceof NetworkError
          ? "Sem conexão — não foi possível avisar agora. Tente de novo."
          : e instanceof ApiError
            ? e.detail
            : "Não foi possível registrar o atraso."
      );
    } finally {
      setEnviandoAtrasoMinutos(null);
    }
  }

  function entrarModoReordenar() {
    setOrdemRascunho(alunosAguardando);
    setErroReordenar(null);
    setMostrarAtraso(false);
    setReordenando(true);
  }

  function cancelarReordenar() {
    setReordenando(false);
    setOrdemRascunho([]);
  }

  function moverNoRascunho(tripStudentId: string, direcao: -1 | 1) {
    setOrdemRascunho((atual) => {
      const indice = atual.findIndex((ts) => ts.id === tripStudentId);
      const novoIndice = indice + direcao;
      if (indice < 0 || novoIndice < 0 || novoIndice >= atual.length) return atual;
      const copia = [...atual];
      [copia[indice], copia[novoIndice]] = [copia[novoIndice], copia[indice]];
      return copia;
    });
  }

  async function concluirReordenar() {
    setSalvandoOrdem(true);
    setErroReordenar(null);
    try {
      // Preserva a ordem relativa dos demais (chegou/a_bordo/etc.) — só o bloco
      // de 'aguardando' é renumerado a partir da posição do primeiro.
      const baseOrdem = alunosAguardando.length > 0 ? alunosAguardando[0].ordem : 0;
      const itens = ordemRascunho.map((ts, indice) => ({ trip_student_id: ts.id, ordem: baseOrdem + indice }));
      await store.reordenar(itens);
      feedbackAceito();
      setReordenando(false);
    } catch (e) {
      feedbackErro();
      setErroReordenar(
        e instanceof NetworkError
          ? "Sem conexão — não é possível reordenar agora."
          : e instanceof ApiError
            ? e.detail
            : "Não foi possível salvar a nova ordem."
      );
    } finally {
      setSalvandoOrdem(false);
    }
  }

  const listaExibida = reordenando ? ordemRascunho : store.tripStudents;

  const renderizarLinha = useCallback(
    ({ item }: { item: TripStudentOut }) => (
      <AlunoRow
        tripStudent={item}
        pendente={(store.pendentesPorTripStudent[item.id] ?? []).length > 0}
        atual={paradaAtual?.alvo.id === item.id}
        reordenando={reordenando}
        onAbrirAcoes={() => setMenuAluno(item)}
        onMoverParaCima={() => moverNoRascunho(item.id, -1)}
        onMoverParaBaixo={() => moverNoRascunho(item.id, 1)}
      />
    ),
    [store.pendentesPorTripStudent, paradaAtual, reordenando]
  );

  return (
    <View style={estilos.tela}>
      <View style={[estilos.cabecalho, { paddingTop: espacamento.md + insets.top }]}>
        <View style={estilos.cabecalhoTopo}>
          <View style={estilos.cabecalhoInfo}>
            <Text style={estilos.nomeRota} numberOfLines={1}>
              {store.viagem?.rota_nome ?? "Viagem"}
            </Text>
            <Text style={estilos.stats}>
              {restantes === 0
                ? "Todos resolvidos"
                : `Faltam ${restantes} de ${store.tripStudents.length}`}
            </Text>
          </View>

          {atraso ? (
            <View style={estilos.selosAtraso}>
              <Text style={estilos.selosAtrasoTexto}>{atraso.toUpperCase()}</Text>
            </View>
          ) : null}
        </View>

        {/* Progresso da rota por paradas resolvidas — responde "onde estou" sem
            exigir leitura de número. */}
        <View style={estilos.trilha} accessibilityRole="progressbar">
          <View
            style={[
              estilos.trilhaPreenchida,
              {
                width:
                  store.tripStudents.length > 0
                    ? `${(resolvidos / store.tripStudents.length) * 100}%`
                    : "0%",
              },
            ]}
          />
        </View>

        {!reordenando ? (
          <View style={estilos.acoesRota}>
            {alunosAguardando.length > 1 ? (
              <LinkToque titulo="Reordenar paradas" cor={cores.info} onPress={entrarModoReordenar} />
            ) : null}
            <LinkToque
              titulo={mostrarAtraso ? "Fechar atraso" : "Estou atrasado"}
              cor={cores.ambar}
              estiloTexto={estilos.linkDireita}
              onPress={() => setMostrarAtraso((atual) => !atual)}
            />
          </View>
        ) : null}
      </View>

      <PillSync />

      {store.erro ? (
        <Banner
          tom="erro"
          mensagem={store.erro}
          acao={{ titulo: "Tentar de novo", onPress: () => void store.recarregar() }}
        />
      ) : null}

      {/* Bloqueio do §7.2 e conflito da fila são a mesma classe de problema —
          mostrar os dois juntos só empurraria a lista para fora da tela. */}
      {bloqueioParadaAnterior ? (
        <Banner
          tom="erro"
          mensagem={bloqueioParadaAnterior}
          acao={{
            titulo: "Ok",
            accessibilityLabel: "Entendi o bloqueio da parada anterior",
            onPress: () => setBloqueioParadaAnterior(null),
          }}
        />
      ) : store.conflito ? (
        <Banner
          tom="erro"
          mensagem={store.conflito}
          acao={{
            titulo: "Ok",
            accessibilityLabel: "Fechar aviso de conflito",
            onPress: store.limparConflito,
          }}
        />
      ) : null}

      {confirmacaoAtraso ? (
        <Banner
          tom="ok"
          mensagem={confirmacaoAtraso}
          acao={{
            titulo: "Ok",
            accessibilityLabel: "Fechar confirmação de atraso",
            onPress: () => setConfirmacaoAtraso(null),
          }}
        />
      ) : null}

      {erroReordenar ? <Banner tom="erro" mensagem={erroReordenar} /> : null}

      {mostrarAtraso ? (
        <View style={estilos.painelAtraso}>
          <Text style={estilos.painelAtrasoTitulo}>EMPURRAR A ROTA EM</Text>
          <View style={estilos.chipsAtraso}>
            {OPCOES_ATRASO_MINUTOS.map((minutos) => (
              <Pressable
                key={minutos}
                accessibilityRole="button"
                accessibilityLabel={`Empurrar a rota em ${minutos} minutos`}
                android_ripple={{ color: cores.overlay }}
                style={({ pressed }) => [estilos.chipAtraso, pressed && estilos.chipAtrasoPressionado]}
                disabled={enviandoAtrasoMinutos != null}
                onPress={() => void marcarAtraso(minutos)}
              >
                <Text style={estilos.chipAtrasoTexto}>
                  {enviandoAtrasoMinutos === minutos ? "..." : `+${minutos}`}
                </Text>
                <Text style={estilos.chipAtrasoUnidade}>min</Text>
              </Pressable>
            ))}
          </View>
          {erroAtraso ? <Text style={estilos.erroInline}>{erroAtraso}</Text> : null}
        </View>
      ) : null}

      <FlatList
        data={listaExibida}
        keyExtractor={(ts) => ts.id}
        contentContainerStyle={estilos.lista}
        renderItem={renderizarLinha}
        refreshControl={
          <RefreshControl
            refreshing={store.carregando}
            onRefresh={() => void store.recarregar()}
            tintColor={cores.marca}
            colors={[cores.marca]}
          />
        }
        ListEmptyComponent={
          !store.carregando ? (
            <Text style={estilos.vazio}>
              {store.erro
                ? "Não foi possível carregar os alunos desta viagem."
                : "Nenhum aluno nesta viagem."}
            </Text>
          ) : null
        }
      />

      {undos.length > 0 ? (
        <View style={estilos.undoWrap}>
          {undos.map((undo) => (
            <BarraUndo
              key={undo.eventId}
              nomeAluno={undo.nomeAluno}
              expiraEm={undo.expiraEm}
              onDesfazer={() => desfazerCheckin(undo.tripStudentId, undo.eventId)}
              onExpirar={() => store.descartarUndo(undo.eventId)}
            />
          ))}
        </View>
      ) : null}

      {reordenando ? (
        <ModoReordenar
          onConcluir={() => void concluirReordenar()}
          onCancelar={cancelarReordenar}
          salvando={salvandoOrdem}
        />
      ) : paradaAtual ? (
        <CardParadaAtual
          alvo={paradaAtual.alvo}
          fase={paradaAtual.fase}
          pendente={(store.pendentesPorTripStudent[paradaAtual.alvo.id] ?? []).length > 0}
          onAcaoPrimaria={() => acaoPrimaria(paradaAtual.alvo)}
          onAbrirAcoes={() => setMenuAluno(paradaAtual.alvo)}
        />
      ) : (
        <View style={[estilos.rodapeFinal, { paddingBottom: espacamento.lg + insets.bottom }]}>
          <Botao56
            titulo="Finalizar viagem"
            variante="primario"
            tamanho="grande"
            detalhe={`${store.tripStudents.filter((ts) => ehTerminal(ts.estado)).length} alunos resolvidos`}
            onPress={() => navigation.navigate("FinalizarViagem", { viagemId })}
          />
        </View>
      )}

      <DialogoCheguei
        visivel={dialogoCheguei != null}
        nomeAluno={dialogoCheguei?.aluno_nome ?? ""}
        endereco={dialogoCheguei?.parada_endereco ?? null}
        onConfirmar={() => void confirmarCheguei()}
        onCancelar={() => setDialogoCheguei(null)}
      />

      <DialogoConfirmacao
        visivel={dialogoAusente != null}
        titulo={dialogoAusente?.aluno_nome ?? ""}
        subtitulo={dialogoAusente?.parada_endereco ?? null}
        rotuloConfirmar="Marcar ausente"
        varianteConfirmar="destrutivo"
        onConfirmar={() => void confirmarAusente()}
        onCancelar={() => setDialogoAusente(null)}
      />

      <DialogoConfirmacao
        visivel={dialogoCheckout != null}
        titulo={dialogoCheckout?.aluno_nome ?? ""}
        // Deliberadamente NÃO usa `parada_endereco`: aquele campo é o ponto de
        // EMBARQUE (snapshot da origem — ver models/trip_student.py). Exibi-lo
        // num desembarque na escola apontaria o motorista para o lugar errado.
        subtitulo="Desembarque — não tem volta"
        rotuloConfirmar="Confirmar desembarque"
        varianteConfirmar="destrutivo"
        onConfirmar={() => void confirmarCheckout()}
        onCancelar={() => setDialogoCheckout(null)}
      />

      <MenuAcoesAluno
        visivel={menuAluno != null}
        nomeAluno={menuAluno?.aluno_nome ?? ""}
        estado={menuAluno?.estado ?? "aguardando"}
        onDesfazerChegada={desfazerChegadaDoMenu}
        onMarcarAusente={pedirAusenteDoMenu}
        onFechar={() => setMenuAluno(null)}
      />
    </View>
  );
}

const criarEstilos = (cores: Paleta) =>
  StyleSheet.create({
    tela: {
      flex: 1,
      backgroundColor: cores.papel,
    },
    cabecalho: {
      paddingHorizontal: espacamento.lg,
      paddingBottom: espacamento.sm,
      backgroundColor: cores.cartao,
      borderBottomWidth: 1,
      borderBottomColor: cores.linha,
    },
    cabecalhoTopo: {
      flexDirection: "row",
      alignItems: "center",
      gap: espacamento.sm,
    },
    cabecalhoInfo: {
      flex: 1,
    },
    nomeRota: {
      fontSize: tipografia.titulo,
      fontWeight: peso.forte,
      color: cores.tinta,
    },
    stats: {
      fontSize: tipografia.endereco,
      color: cores.esmaecido,
      marginTop: 1,
    },
    selosAtraso: {
      backgroundColor: cores.ambarSuave,
      borderWidth: 1,
      borderColor: cores.ambarBorda,
      borderRadius: raio.pilula,
      paddingVertical: 5,
      paddingHorizontal: espacamento.md,
    },
    selosAtrasoTexto: {
      fontSize: tipografia.legenda,
      fontWeight: peso.forte,
      letterSpacing: ESPACO_LETRA_SELO,
      color: cores.ambar,
    },
    trilha: {
      height: 4,
      borderRadius: raio.pilula,
      backgroundColor: cores.linha,
      marginTop: espacamento.md,
      overflow: "hidden",
    },
    trilhaPreenchida: {
      height: 4,
      borderRadius: raio.pilula,
      backgroundColor: cores.marca,
    },
    acoesRota: {
      flexDirection: "row",
      alignItems: "center",
    },
    linkDireita: {
      marginLeft: "auto",
    },
    painelAtraso: {
      backgroundColor: cores.ambarSuave,
      borderWidth: 1,
      borderColor: cores.ambarBorda,
      marginHorizontal: espacamento.lg,
      marginTop: espacamento.sm,
      borderRadius: raio.md,
      padding: espacamento.md,
    },
    painelAtrasoTitulo: {
      fontSize: tipografia.legenda,
      fontWeight: peso.forte,
      letterSpacing: ESPACO_LETRA_SELO,
      color: cores.ambar,
      marginBottom: espacamento.sm,
    },
    chipsAtraso: {
      flexDirection: "row",
      gap: espacamento.sm,
    },
    chipAtraso: {
      flex: 1,
      minHeight: TOQUE_MIN,
      alignItems: "center",
      justifyContent: "center",
      borderRadius: raio.md,
      backgroundColor: cores.cartao,
      borderWidth: 1,
      borderColor: cores.ambarBorda,
      overflow: "hidden",
    },
    chipAtrasoPressionado: {
      opacity: 0.7,
    },
    chipAtrasoTexto: {
      fontSize: tipografia.subtitulo,
      fontWeight: peso.forte,
      color: cores.ambar,
    },
    chipAtrasoUnidade: {
      fontSize: tipografia.legenda,
      color: cores.ambar,
      opacity: 0.8,
    },
    erroInline: {
      color: cores.perigo,
      fontSize: tipografia.legenda,
      fontWeight: peso.forte,
      paddingTop: espacamento.sm,
    },
    lista: {
      paddingHorizontal: espacamento.lg,
      paddingTop: espacamento.md,
      paddingBottom: espacamento.lg,
      flexGrow: 1,
    },
    vazio: {
      color: cores.dica,
      textAlign: "center",
      marginTop: espacamento.xl,
      fontSize: tipografia.endereco,
    },
    undoWrap: {
      paddingHorizontal: espacamento.lg,
    },
    rodapeFinal: {
      padding: espacamento.lg,
      backgroundColor: cores.cartao,
      borderTopWidth: 1,
      borderTopColor: cores.linha2,
      borderTopLeftRadius: raio.lg,
      borderTopRightRadius: raio.lg,
    },
  });
