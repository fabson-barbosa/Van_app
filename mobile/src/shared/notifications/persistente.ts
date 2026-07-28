/**
 * Notificação persistente de "chegamos, estamos esperando" (CLAUDE.md §5).
 *
 * Decisão do usuário sobre a fidelidade do timer: `usesChronometer`/
 * `showWhen` do `Notification.Builder` nativo NÃO são expostos pela API
 * cross-platform do `expo-notifications` (confirmado na doc oficial antes
 * de codar) — exigiria um native module próprio, ou seja, sair do Expo Go.
 * Fallback adotado (aprovado como obrigatório): `sticky: true` garante que
 * a notificação nunca some sozinha (essencial); o texto mostra o horário
 * fixo da chegada e, como bônus sem custo de infra, é reescrito a cada
 * ~45s enquanto o app está vivo (foreground ou background recente),
 * mostrando minutos decorridos por cima do horário fixo — não é um
 * cronômetro nativo por segundo, mas conta de verdade.
 *
 * A tela de acompanhamento (`AcompanharFilhoScreen`) mostra o cronômetro
 * exato em tempo real via JS puro — essa notificação é só o resumo pra
 * fora do app.
 */
import * as Notifications from "expo-notifications";
import { Platform } from "react-native";

import { CANAL_CHEGADA } from "./canal";

const REFRESH_MS = 45_000;

interface ChegadaAtiva {
  intervalId: ReturnType<typeof setInterval>;
  chegouEmMs: number;
  horarioFormatado: string;
}

const ativos = new Map<string, ChegadaAtiva>();

function identificador(tripStudentId: string): string {
  return `chegada-${tripStudentId}`;
}

function formatarHorario(data: Date): string {
  return data.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

function textoCorpo(chegouEmMs: number, horarioFormatado: string): string {
  const minutos = Math.max(0, Math.floor((Date.now() - chegouEmMs) / 60_000));
  const espera = minutos <= 0 ? "há poucos instantes" : `há ${minutos} min`;
  return `Chegamos às ${horarioFormatado} — esperando ${espera}.`;
}

async function escrever(tripStudentId: string, chegouEmMs: number, horarioFormatado: string): Promise<void> {
  await Notifications.scheduleNotificationAsync({
    identifier: identificador(tripStudentId),
    content: {
      title: "Chegamos!",
      body: textoCorpo(chegouEmMs, horarioFormatado),
      sticky: true,
      autoDismiss: false,
      data: { tipo: "chegada", trip_student_id: tripStudentId },
      ...(Platform.OS === "android" ? { channelId: CANAL_CHEGADA } : {}),
    },
    trigger: null,
  });
}

/** Idempotente — chamar de novo pro mesmo `tripStudentId` (ex.: app reaberto
 * com a notificação ainda pendente) reinicia o ciclo de refresh sem duplicar
 * a notificação (mesmo `identifier` = substitui, nunca empilha). */
export async function mostrarOuAtualizarChegada(tripStudentId: string, chegouEmIso: string): Promise<void> {
  const chegouEmMs = new Date(chegouEmIso).getTime();
  const horarioFormatado = formatarHorario(new Date(chegouEmMs));

  const existente = ativos.get(tripStudentId);
  if (existente) clearInterval(existente.intervalId);

  await escrever(tripStudentId, chegouEmMs, horarioFormatado);
  const intervalId = setInterval(() => {
    void escrever(tripStudentId, chegouEmMs, horarioFormatado);
  }, REFRESH_MS);
  ativos.set(tripStudentId, { intervalId, chegouEmMs, horarioFormatado });
}

/** Chamado pelo sinal `dismiss_chegada` (push silencioso do backend quando o
 * aluno sai de `chegou` — Checkin ou Ausente) e também localmente quando a
 * tela de acompanhamento detecta a mesma mudança de estado. */
export async function dispensarChegada(tripStudentId: string): Promise<void> {
  const existente = ativos.get(tripStudentId);
  if (existente) {
    clearInterval(existente.intervalId);
    ativos.delete(tripStudentId);
  }
  try {
    await Notifications.dismissNotificationAsync(identificador(tripStudentId));
  } catch {
    // já dispensada ou nunca existiu nesta sessão do app — no-op.
  }
}
