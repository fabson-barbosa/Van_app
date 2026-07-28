/**
 * Registro do token de push (Bloco B5). Decisão do usuário: Expo Push
 * Service, não FCM direto — o app roda em Expo Go (sem dev client
 * custom), e token nativo de FCM não funciona nesse modo.
 *
 * `getExpoPushTokenAsync` exige um `projectId` de um projeto EAS mesmo
 * dentro do Expo Go (registro gratuito, `eas init`, sem build). Tratado
 * como best-effort: sem `projectId` configurado, ou sem permissão, ou em
 * emulador — o app funciona normalmente, só sem push (a tela de
 * acompanhamento continua atualizando por pull-to-refresh).
 */
import Constants from "expo-constants";
import * as Device from "expo-device";
import * as Notifications from "expo-notifications";

import { endpoints } from "../api/endpoints";

let tokenAtual: string | null = null;

function obterProjectId(): string | null {
  const extra = Constants.expoConfig?.extra as { eas?: { projectId?: string } } | undefined;
  return extra?.eas?.projectId ?? Constants.easConfig?.projectId ?? null;
}

export async function registrarPushToken(): Promise<string | null> {
  if (!Device.isDevice) {
    console.warn("[push] desativado: emulador/simulador não recebe push de verdade.");
    return null;
  }

  const atual = await Notifications.getPermissionsAsync();
  let status = atual.status;
  if (status !== "granted") {
    const pedido = await Notifications.requestPermissionsAsync();
    status = pedido.status;
  }
  if (status !== "granted") {
    console.warn("[push] desativado: permissão de notificação negada.");
    return null;
  }

  const projectId = obterProjectId();
  if (!projectId) {
    console.warn("[push] desativado: nenhum EAS projectId configurado (rode `eas init` em mobile/).");
    return null;
  }

  try {
    const { data: token } = await Notifications.getExpoPushTokenAsync({ projectId });
    await endpoints.registrarTokenPush({ token, provider: "expo" });
    tokenAtual = token;
    return token;
  } catch (erro) {
    console.warn("[push] falha ao registrar token.", erro);
    return null;
  }
}

/** Best-effort — falha aqui nunca deve travar o logout. */
export async function removerPushTokenAtual(): Promise<void> {
  if (!tokenAtual) return;
  const token = tokenAtual;
  tokenAtual = null;
  try {
    await endpoints.removerTokenPush(token);
  } catch (erro) {
    console.warn("[push] falha ao remover token no logout — token expira sozinho quando o Expo o marcar morto.", erro);
  }
}
