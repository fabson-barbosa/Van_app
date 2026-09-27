/**
 * Resolução de modo de tema (Bloco B8).
 *
 * `resolverPaleta` é a única regra do tema que tem como estar errada de um jeito
 * que o usuário percebe: escolher "Claro" e receber escuro porque o Android está
 * em escuro, ou o `automatico` cair em escuro num aparelho antigo que não reporta
 * esquema nenhum (`useColorScheme()` devolve `null`).
 */
import { ehModoValido, resolverPaleta } from "../TemaContext";

describe("resolverPaleta", () => {
  it("escolha explícita ganha do sistema", () => {
    expect(resolverPaleta("claro", "dark").nome).toBe("claro");
    expect(resolverPaleta("escuro", "light").nome).toBe("escuro");
  });

  it("automático segue o Android", () => {
    expect(resolverPaleta("automatico", "dark").nome).toBe("escuro");
    expect(resolverPaleta("automatico", "light").nome).toBe("claro");
  });

  // `useColorScheme()` devolve `null` em aparelho/versão sem tema escuro no
  // sistema — justamente o parque de aparelhos antigos do CLAUDE.md §2. Cair em
  // escuro ali seria uma surpresa para quem nunca pediu nada.
  it("automático cai em claro quando o sistema não informa esquema", () => {
    expect(resolverPaleta("automatico", null).nome).toBe("claro");
    expect(resolverPaleta("automatico", undefined).nome).toBe("claro");
  });
});

describe("ehModoValido", () => {
  it("aceita os três modos", () => {
    expect(ehModoValido("claro")).toBe(true);
    expect(ehModoValido("escuro")).toBe(true);
    expect(ehModoValido("automatico")).toBe(true);
  });

  // O valor vem do AsyncStorage, que é texto livre: uma versão futura que renomeie
  // um modo encontraria o nome antigo salvo no aparelho e tem que ignorá-lo em vez
  // de deixar o tema indefinido.
  it("rejeita lixo salvo no aparelho", () => {
    expect(ehModoValido("dark")).toBe(false);
    expect(ehModoValido("")).toBe(false);
    expect(ehModoValido(null)).toBe(false);
    expect(ehModoValido(undefined)).toBe(false);
    expect(ehModoValido(1)).toBe(false);
  });
});
