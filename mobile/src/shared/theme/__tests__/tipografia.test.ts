/**
 * Trava do piso tipográfico (Bloco B8).
 *
 * CLAUDE.md §8 fixa **13sp** como piso: a tela é lida sob sol direto, em
 * aparelho antigo. O B7 declarou esse piso na especificação e ajustou a escala
 * em `tokens.ts` — mas os componentes continuaram com números crus nos
 * `StyleSheet`, e sobraram `12.5` no `EstadoBadge`, `12` no `PillSync` e `11.5`
 * na tela de finalizar viagem. Uma regra que vive só na prosa não se cumpre.
 *
 * Este teste varre o código-fonte. Não é elegante — teste lendo arquivo com
 * `fs` —, mas é o único jeito de pegar a classe inteira do erro em vez de um
 * caso por vez: `fontSize` entra em `StyleSheet.create`, que nenhum teste de
 * comportamento observa, e o TypeScript aceita qualquer número.
 *
 * Escopo: o Motorista (alvo do B8) e os componentes compartilhados. As telas do
 * Responsável e o Login ficaram fora da reconstrução por decisão de escopo e
 * ainda têm literais abaixo do piso — entram aqui junto com o bloco que as
 * redesenhar.
 */
import fs from "fs";
import path from "path";

import { tipografia } from "../tokens";

const RAIZ = path.resolve(__dirname, "..", "..", "..");

const PASTAS_COBERTAS = ["motorista", path.join("shared", "components"), path.join("shared", "feedback")];

/** Pesos que o Android antigo não tem arquivo para: sem a família variável
 * instalada, o sistema arredonda para regular e a hierarquia desenhada no
 * emulador desaparece no aparelho do motorista. Ver `tokens.ts`. */
const PESOS_PROIBIDOS = ["100", "200", "300", "500", "600", "800", "900"];

function arquivosFonte(): string[] {
  const encontrados: string[] = [];

  function varrer(dir: string): void {
    for (const entrada of fs.readdirSync(dir, { withFileTypes: true })) {
      const completo = path.join(dir, entrada.name);
      if (entrada.isDirectory()) {
        if (entrada.name !== "__tests__") varrer(completo);
      } else if (/\.tsx?$/.test(entrada.name)) {
        encontrados.push(completo);
      }
    }
  }

  for (const pasta of PASTAS_COBERTAS) varrer(path.join(RAIZ, pasta));
  return encontrados;
}

/** Remove comentários antes de procurar padrões, para a prosa que EXPLICA a
 * regra (inclusive as docstrings que citam `fontSize: 12.5`) não a violar. */
function semComentarios(conteudo: string): string {
  return conteudo.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
}

describe("escala tipográfica", () => {
  it("nenhum tamanho da escala fica abaixo do piso de 13sp (CLAUDE.md §8)", () => {
    for (const [nome, valor] of Object.entries(tipografia)) {
      expect({ nome, valor }).toMatchObject({ valor: expect.any(Number) });
      expect(valor).toBeGreaterThanOrEqual(13);
    }
  });

  it("a escala é estritamente decrescente do maior ao menor", () => {
    const valores = Object.values(tipografia);
    for (let i = 1; i < valores.length; i += 1) {
      expect(valores[i]).toBeLessThan(valores[i - 1]);
    }
  });
});

describe("código do Motorista e componentes compartilhados", () => {
  const arquivos = arquivosFonte();

  it("encontra os arquivos a varrer", () => {
    expect(arquivos.length).toBeGreaterThan(8);
  });

  it("não usa nenhum fontSize numérico cru — o tamanho sai de `tipografia`", () => {
    const infratores: string[] = [];

    for (const arquivo of arquivos) {
      const linhas = semComentarios(fs.readFileSync(arquivo, "utf8")).split("\n");
      linhas.forEach((linha, indice) => {
        const achado = linha.match(/fontSize:\s*([0-9.]+)/);
        if (achado) {
          infratores.push(`${path.relative(RAIZ, arquivo)}:${indice + 1} -> fontSize: ${achado[1]}`);
        }
      });
    }

    expect(infratores).toEqual([]);
  });

  it("não usa peso de fonte que o Android antigo arredonda", () => {
    const infratores: string[] = [];

    for (const arquivo of arquivos) {
      const linhas = semComentarios(fs.readFileSync(arquivo, "utf8")).split("\n");
      linhas.forEach((linha, indice) => {
        const achado = linha.match(/fontWeight:\s*"([0-9]+)"/);
        if (achado && PESOS_PROIBIDOS.includes(achado[1])) {
          infratores.push(`${path.relative(RAIZ, arquivo)}:${indice + 1} -> fontWeight: "${achado[1]}"`);
        }
      });
    }

    expect(infratores).toEqual([]);
  });

  /**
   * Cor crua num `StyleSheet` é o que impede o tema escuro de funcionar: o valor
   * fica congelado na folha de estilo e não acompanha a paleta. Foi exatamente
   * assim que o app chegou aqui — `"#ffffff"` fixo como cor de texto do botão
   * primário, que no escuro fica branco sobre verde claro.
   */
  it("não usa cor hexadecimal crua — a cor sai da paleta", () => {
    const infratores: string[] = [];

    for (const arquivo of arquivos) {
      const linhas = semComentarios(fs.readFileSync(arquivo, "utf8")).split("\n");
      linhas.forEach((linha, indice) => {
        const achado = linha.match(/#[0-9a-fA-F]{3,8}\b/);
        if (achado) {
          infratores.push(`${path.relative(RAIZ, arquivo)}:${indice + 1} -> ${achado[0]}`);
        }
      });
    }

    expect(infratores).toEqual([]);
  });
});
