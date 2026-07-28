/** Canais de notificação Android (obrigatório desde Android 8 — sem canal,
 * não há como diferenciar importância por tipo). Um canal por tipo da
 * cascata (CLAUDE.md §5): `chegada` é a mais importante (persistente, tempo
 * de espera correndo — precisa interromper), `preparo` é a mais leve
 * ("faltam ~X min", informativa). */
import * as Notifications from "expo-notifications";
import { Platform } from "react-native";

export const CANAL_CHEGADA = "chegada";
export const CANAL_IMINENCIA = "iminencia";
export const CANAL_PREPARO = "preparo";

export async function configurarCanaisAndroid(): Promise<void> {
  if (Platform.OS !== "android") return;

  await Notifications.setNotificationChannelAsync(CANAL_CHEGADA, {
    name: "Chegamos na parada",
    importance: Notifications.AndroidImportance.MAX,
    sound: "default",
    vibrationPattern: [0, 250, 250, 250],
    lockscreenVisibility: Notifications.AndroidNotificationVisibility.PUBLIC,
  });
  await Notifications.setNotificationChannelAsync(CANAL_IMINENCIA, {
    name: "É a próxima parada",
    importance: Notifications.AndroidImportance.HIGH,
    sound: "default",
  });
  await Notifications.setNotificationChannelAsync(CANAL_PREPARO, {
    name: "Prepare-se",
    importance: Notifications.AndroidImportance.DEFAULT,
  });
}
