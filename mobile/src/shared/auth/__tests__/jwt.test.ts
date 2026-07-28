import { decodeJwtPayload } from "../jwt";

/** Monta um JWT sintático válido (header.payload.assinatura) — a assinatura
 * não importa pra este módulo, que nunca a verifica (decisão documentada:
 * só decide qual stack de UI mostrar). Usa `Buffer` (disponível no processo
 * Node do Jest) só pra montar o fixture — o módulo em si não depende dele. */
function montarJwt(payload: Record<string, unknown>): string {
  const base64Url = (obj: unknown) =>
    Buffer.from(JSON.stringify(obj)).toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  return `${base64Url({ alg: "HS256", typ: "JWT" })}.${base64Url(payload)}.assinatura-fake`;
}

describe("decodeJwtPayload", () => {
  it("decodifica o payload de um JWT bem formado", () => {
    const token = montarJwt({ sub: "user-1", role: "responsavel", tenant_id: "tenant-1" });
    expect(decodeJwtPayload(token)).toEqual({ sub: "user-1", role: "responsavel", tenant_id: "tenant-1" });
  });

  it("preserva caracteres UTF-8 (ex.: nome com acento)", () => {
    const token = montarJwt({ nome: "João Ângelo" });
    expect(decodeJwtPayload(token)).toEqual({ nome: "João Ângelo" });
  });

  it("devolve null para token sem 3 segmentos", () => {
    expect(decodeJwtPayload("token-invalido")).toBeNull();
  });

  it("devolve null para segmento de payload que não é JSON válido", () => {
    expect(decodeJwtPayload("cabecalho.!!!nao-e-base64-json!!!.assinatura")).toBeNull();
  });

  it("devolve null para string vazia", () => {
    expect(decodeJwtPayload("")).toBeNull();
  });
});
