/**
 * Decodifica o PAYLOAD de um JWT sem verificar assinatura — usado só pra
 * extrair claims de UI (ex.: `role`, pra o RootNavigator escolher a stack
 * Motorista ou Responsável). Nunca é fonte de autorização: o backend valida
 * a assinatura e o RBAC de verdade em cada request (`app/api/deps.py`).
 *
 * Implementação própria (sem depender de `atob`/`Buffer`) porque nem todo
 * runtime Hermes/Expo Go garante esses globais — mesma cautela do resto do
 * app (ver bugs encontrados em aparelho físico real no Bloco B4).
 */
const BASE64_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

function base64UrlDecode(segmento: string): string {
  const base64 = segmento.replace(/-/g, "+").replace(/_/g, "/");
  const preenchido = base64 + "=".repeat((4 - (base64.length % 4)) % 4);
  let resultado = "";
  let buffer = 0;
  let bits = 0;
  for (const char of preenchido) {
    if (char === "=") break;
    const valor = BASE64_CHARS.indexOf(char);
    if (valor === -1) continue;
    buffer = (buffer << 6) | valor;
    bits += 6;
    if (bits >= 8) {
      bits -= 8;
      resultado += String.fromCharCode((buffer >> bits) & 0xff);
    }
  }
  return resultado;
}

export function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const partes = token.split(".");
    if (partes.length !== 3) return null;
    const bruto = base64UrlDecode(partes[1]);
    const utf8 = decodeURIComponent(
      bruto
        .split("")
        .map((c) => "%" + c.charCodeAt(0).toString(16).padStart(2, "0"))
        .join("")
    );
    return JSON.parse(utf8) as Record<string, unknown>;
  } catch {
    return null;
  }
}
