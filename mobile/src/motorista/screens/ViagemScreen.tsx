/** Tela 3 — Viagem em andamento: lista de alunos com estado visível. */
import React, { useMemo, useState } from "react";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { Alert, FlatList, Pressable, StyleSheet, Text, View } from "react-native";

import { ApiError, NetworkError } from "../../shared/api/client";
import { endpoints } from "../../shared/api/endpoints";
import { Botao56 } from "../../shared/components/Botao56";
import { PillSync } from "../../shared/components/PillSync";
import { TOQUE_MIN, cores, espacamento, raio, tipografia } from "../../shared/theme";
import type { RootStackParamList } from "../../navigation/RootNavigator";
import { AlunoRow } from "../components/AlunoRow";
import { BarraUndo } from "../components/BarraUndo";
import { DialogoCheguei } from "../components/DialogoCheguei";
import { ModoReordenar } from "../components/ModoReordenar";
import { useViagemStore } from "../state/ViagemStore";
import type { TripStudentOut } from "../../shared/api/types";

const OPCOES_ATRASO_MINUTOS = [5, 10, 15, 20];

type Props = NativeStackScreenProps<RootStackParamList, "Viagem">;

interface EstadoUndo {
  tripStudentId: string;
  nomeAluno: string;
  eventId: string;
}

export function ViagemScreen({ route, navigation }: Props): React.JSX.Element {
  const { viagemId } = route.params;
  const store = useViagemStore(viagemId);

  const [dialogoCheguei, setDialogoCheguei] = useState<TripStudentOut | null>(null);
  const [undo, setUndo] = useState<EstadoUndo | null>(null);
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

  const embarcados = useMemo(
    () => store.tripStudents.filter((ts) => ts.estado === "a_bordo" || ts.estado === "entregue").length,
    [store.tripStudents]
  );

  function solicitarCheguei(tripStudent: TripStudentOut) {
    // §7.2 (CLAUDE.md) — guard de UI espelhando o 409 ParadaAnteriorPendenteError.
    const pendentes = store.paradasAnterioresPendentes(tripStudent.id);
    if (pendentes.length > 0) {
      const nomes = pendentes.map((p) => `${p.ordem}. ${p.aluno_nome}`).join("\n");
      Alert.alert(
        "Resolva a parada anterior primeiro",
        `Confirme o Checkin ou marque Ausente para:\n\n${nomes}`,
        [{ text: "Entendi" }]
      );
      return;
    }
    setDialogoCheguei(tripStudent);
  }

  async function confirmarCheguei() {
    if (!dialogoCheguei) return;
    const alvo = dialogoCheguei;
    setDialogoCheguei(null);
    await store.marcarCheguei(alvo.id);
  }

  /** "Estou atrasado" (CLAUDE.md §5) — empurra a cauda manualmente e
   * reagenda os avisos pendentes. Online-only (mesmo padrão de reordenar/
   * iniciar/finalizar — ação de fronteira, rara, precisa da resposta do
   * servidor pra fazer sentido), então não passa pela fila offline. */
  async function marcarAtraso(minutos: number) {
    setEnviandoAtrasoMinutos(minutos);
    setErroAtraso(null);
    try {
      await endpoints.estouAtrasado(viagemId, { minutos });
      setConfirmacaoAtraso(`Avisamos os responsáveis pendentes: +${minutos} min na rota.`);
      setMostrarAtraso(false);
    } catch (e) {
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

  async function fazerCheckin(tripStudent: TripStudentOut) {
    const eventId = await store.marcarCheckin(tripStudent.id);
    setUndo({ tripStudentId: tripStudent.id, nomeAluno: tripStudent.aluno_nome, eventId });
  }

  async function desfazerCheckinAtivo() {
    if (!undo) return;
    const alvo = undo;
    setUndo(null);
    await store.desfazerCheckin(alvo.tripStudentId, alvo.eventId);
  }

  function confirmarAusente(tripStudent: TripStudentOut) {
    // Um toque, sem diálogo (CLAUDE.md §8) — nenhuma confirmação aqui de propósito.
    void store.marcarAusente(tripStudent.id);
  }

  function entrarModoReordenar() {
    setOrdemRascunho(alunosAguardando);
    setErroReordenar(null);
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
      // Preserva a ordem relativa dos demais (chegou/a_bordo/etc.) — só o
      // bloco de 'aguardando' é renumerado a partir da posição do primeiro.
      const baseOrdem = alunosAguardando.length > 0 ? alunosAguardando[0].ordem : 0;
      const itens = ordemRascunho.map((ts, indice) => ({ trip_student_id: ts.id, ordem: baseOrdem + indice }));
      await store.reordenar(itens);
      setReordenando(false);
    } catch (e) {
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

  return (
    <View style={estilos.tela}>
      <View style={estilos.cabecalho}>
        <View style={estilos.linhaTitulo}>
          <Text style={estilos.nomeRota} numberOfLines={1}>
            {store.viagem?.rota_nome ?? "Viagem"}
          </Text>
          <Text style={estilos.linkAtraso} onPress={() => setMostrarAtraso((atual) => !atual)}>
            Estou atrasado
          </Text>
        </View>
        <Text style={estilos.stats}>
          {embarcados} / {store.tripStudents.length} concluídos
        </Text>
      </View>

      {mostrarAtraso ? (
        <View style={estilos.painelAtraso}>
          <Text style={estilos.painelAtrasoTitulo}>Empurrar a rota em quantos minutos?</Text>
          <View style={estilos.chipsAtraso}>
            {OPCOES_ATRASO_MINUTOS.map((minutos) => (
              <Pressable
                key={minutos}
                accessibilityRole="button"
                style={({ pressed }) => [estilos.chipAtraso, pressed && estilos.chipAtrasoPressionado]}
                disabled={enviandoAtrasoMinutos != null}
                onPress={() => void marcarAtraso(minutos)}
              >
                <Text style={estilos.chipAtrasoTexto}>
                  {enviandoAtrasoMinutos === minutos ? "..." : `+${minutos} min`}
                </Text>
              </Pressable>
            ))}
          </View>
          {erroAtraso ? <Text style={estilos.erroReordenar}>{erroAtraso}</Text> : null}
        </View>
      ) : null}

      {confirmacaoAtraso ? (
        <View style={estilos.bannerConfirmacaoAtraso}>
          <Text style={estilos.bannerConfirmacaoAtrasoTexto}>{confirmacaoAtraso}</Text>
          <Text style={estilos.bannerConflitoFechar} onPress={() => setConfirmacaoAtraso(null)}>
            Ok
          </Text>
        </View>
      ) : null}

      <PillSync />

      {store.conflito ? (
        <View style={estilos.bannerConflito}>
          <Text style={estilos.bannerConflitoTexto} numberOfLines={2}>
            {store.conflito}
          </Text>
          <Text style={estilos.bannerConflitoFechar} onPress={store.limparConflito}>
            Ok
          </Text>
        </View>
      ) : null}

      {undo ? (
        <View style={estilos.undoWrap}>
          <BarraUndo
            key={undo.eventId}
            nomeAluno={undo.nomeAluno}
            onDesfazer={() => void desfazerCheckinAtivo()}
            onExpirar={() => setUndo(null)}
          />
        </View>
      ) : null}

      {erroReordenar ? <Text style={estilos.erroReordenar}>{erroReordenar}</Text> : null}

      <FlatList
        data={listaExibida}
        keyExtractor={(ts) => ts.id}
        contentContainerStyle={estilos.lista}
        renderItem={({ item }) => (
          <AlunoRow
            tripStudent={item}
            pendente={(store.pendentesPorTripStudent[item.id] ?? []).length > 0}
            reordenando={reordenando}
            onSolicitarCheguei={() => solicitarCheguei(item)}
            onCheckin={() => void fazerCheckin(item)}
            onCheckout={() => void store.marcarCheckout(item.id)}
            onAusente={() => confirmarAusente(item)}
            onMoverParaCima={() => moverNoRascunho(item.id, -1)}
            onMoverParaBaixo={() => moverNoRascunho(item.id, 1)}
          />
        )}
      />

      {reordenando ? (
        <ModoReordenar onConcluir={() => void concluirReordenar()} onCancelar={cancelarReordenar} salvando={salvandoOrdem} />
      ) : (
        <View style={estilos.rodape}>
          {alunosAguardando.length > 1 ? (
            <Text style={estilos.linkReordenar} onPress={entrarModoReordenar}>
              Reordenar paradas
            </Text>
          ) : null}
          <Botao56
            titulo="Finalizar viagem"
            variante="perigo"
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
    </View>
  );
}

const estilos = StyleSheet.create({
  tela: {
    flex: 1,
    backgroundColor: cores.papel,
  },
  cabecalho: {
    paddingHorizontal: espacamento.lg,
    paddingTop: espacamento.xl,
    paddingBottom: espacamento.sm,
  },
  linhaTitulo: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: espacamento.sm,
  },
  linkAtraso: {
    fontSize: 13,
    fontWeight: "700",
    color: cores.ambar,
  },
  painelAtraso: {
    backgroundColor: cores.ambarSuave,
    marginHorizontal: espacamento.lg,
    marginTop: espacamento.sm,
    borderRadius: raio.md,
    padding: espacamento.md,
  },
  painelAtrasoTitulo: {
    fontSize: 12.5,
    fontWeight: "700",
    color: cores.ambar,
    marginBottom: espacamento.sm,
  },
  chipsAtraso: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: espacamento.sm,
  },
  chipAtraso: {
    minHeight: TOQUE_MIN,
    minWidth: 76,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: raio.md,
    backgroundColor: cores.cartao,
    borderWidth: 1,
    borderColor: cores.ambar,
    paddingHorizontal: espacamento.md,
  },
  chipAtrasoPressionado: {
    opacity: 0.7,
  },
  chipAtrasoTexto: {
    fontSize: tipografia.corpo,
    fontWeight: "700",
    color: cores.ambar,
  },
  bannerConfirmacaoAtraso: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: cores.marcaSuave,
    marginHorizontal: espacamento.lg,
    marginTop: espacamento.sm,
    borderRadius: 10,
    paddingVertical: espacamento.sm,
    paddingHorizontal: espacamento.md,
  },
  bannerConfirmacaoAtrasoTexto: {
    flex: 1,
    fontSize: 12.5,
    color: cores.marca,
    fontWeight: "600",
  },
  nomeRota: {
    fontSize: tipografia.titulo,
    fontWeight: "700",
    color: cores.tinta,
  },
  stats: {
    fontSize: 12.5,
    color: cores.esmaecido,
    marginTop: 2,
  },
  bannerConflito: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: cores.perigoSuave,
    marginHorizontal: espacamento.lg,
    marginTop: espacamento.sm,
    borderRadius: 10,
    paddingVertical: espacamento.sm,
    paddingHorizontal: espacamento.md,
  },
  bannerConflitoTexto: {
    flex: 1,
    fontSize: 12.5,
    color: cores.perigo,
    fontWeight: "600",
  },
  bannerConflitoFechar: {
    fontSize: 13,
    fontWeight: "700",
    color: cores.perigo,
    paddingLeft: espacamento.md,
  },
  undoWrap: {
    paddingHorizontal: espacamento.lg,
    paddingTop: espacamento.sm,
  },
  erroReordenar: {
    color: cores.perigo,
    fontSize: 12.5,
    fontWeight: "600",
    paddingHorizontal: espacamento.lg,
    paddingTop: espacamento.sm,
  },
  lista: {
    padding: espacamento.lg,
  },
  rodape: {
    padding: espacamento.lg,
    gap: espacamento.sm,
  },
  linkReordenar: {
    textAlign: "center",
    fontSize: 13,
    fontWeight: "600",
    color: cores.info,
    marginBottom: espacamento.xs,
  },
});
