/**
 * Ponto de entrada da infra de push (Bloco B5). Chamado uma vez pelo
 * `RootNavigator` (`inicializarNotificacoes`) quando o usuário está
 * autenticado — registra os listeners de recebimento/toque e o handler de
 * primeiro plano.
 */
import * as Notifications from "expo-notifications";

import { navegarParaFilho } from "../../navigation/navigationRef";
import type { PushDataCascata } from "../api/types";
import { configurarCanaisAndroid } from "./canal";
import { dispensarChegada, mostrarOuAtualizarChegada } from "./persistente";

export { CANAL_CHEGADA, CANAL_IMINENCIA, CANAL_PREPARO } from "./canal";
export { registrarPushToken, removerPushTokenAtual } from "./token";

// Primeiro plano: decide se o SO mostra a notificação (CLAUDE.md não pede
// silenciar nada em foreground — as 3 são relevantes o suficiente pra
// interromper mesmo com o app aberto).
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

function comoPushData(valor: unknown): PushDataCascata | undefined {
  if (!valor || typeof valor !== "object" || !("tipo" in valor)) return undefined;
  return valor as PushDataCascata;
}

async function tratarDadosRecebidos(dados: PushDataCascata | undefined): Promise<void> {
  if (!dados?.trip_student_id) return;
  if (dados.tipo === "chegada") {
    await mostrarOuAtualizarChegada(dados.trip_student_id, dados.chegou_em ?? new Date().toISOString());
  }
  if (dados.tipo === "dismiss_chegada") {
    await dispensarChegada(dados.trip_student_id);
  }
}

function tratarToque(dados: PushDataCascata | undefined): void {
  // Sem nome do filho no payload de propósito (minimização — o push só
  // carrega ids); a tela resolve o nome sozinha (`endpoints.listarFilhos`).
  if (dados?.aluno_id) navegarParaFilho(dados.aluno_id);
}

let respostaInicialTratada = false;

/** Retorna a função de limpeza — chamar no `useEffect` de cleanup do
 * `RootNavigator`. Seguro chamar mais de uma vez (ex.: reautenticação). */
export function inicializarNotificacoes(): () => void {
  void configurarCanaisAndroid();

  const assinaturaRecebida = Notifications.addNotificationReceivedListener((evento) => {
    void tratarDadosRecebidos(comoPushData(evento.request.content.data));
  });
  const assinaturaResposta = Notifications.addNotificationResponseReceivedListener((resposta) => {
    tratarToque(comoPushData(resposta.notification.request.content.data));
  });

  // App aberto TOCANDO numa notificação (estava morto/background) — o
  // listener acima só pega toques que acontecem DEPOIS de montado.
  if (!respostaInicialTratada) {
    respostaInicialTratada = true;
    void Notifications.getLastNotificationResponseAsync().then((resposta) => {
      if (resposta) tratarToque(comoPushData(resposta.notification.request.content.data));
    });
  }

  return () => {
    assinaturaRecebida.remove();
    assinaturaResposta.remove();
  };
}
