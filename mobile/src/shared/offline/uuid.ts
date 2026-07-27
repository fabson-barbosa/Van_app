import * as Crypto from "expo-crypto";

/** Isolado num módulo próprio pra ser fácil de mockar nos testes de `queue`/`sync`. */
export function gerarUuid(): string {
  return Crypto.randomUUID();
}
