/**
 * Trava de contraste WCAG AA das duas paletas (Bloco B8).
 *
 * CLAUDE.md §8 exige contraste AA: a tela é lida sob sol direto, em aparelho
 * antigo. O B7 mediu isso à mão e anotou os valores num documento — e sobrou
 * cor reprovada mesmo assim. Com duas paletas o olho não dá conta: a mesma cor
 * de marca que passa sobre creme tem 1,7:1 sobre grafite.
 *
 * Aqui todo par texto/fundo que o app realmente desenha é medido. Se alguém
 * ajustar uma cor "só um tom", o teste diz qual par quebrou e por quanto.
 */
import { AA_TEXTO_GRANDE, AA_TEXTO_NORMAL, razaoContraste } from "../contraste";
import { type Paleta, paletaClara, paletaEscura } from "../paleta";

/** Pares que carregam TEXTO pequeno (< 18pt) — exigem 4,5:1. */
function paresDeTexto(c: Paleta): [string, string, string][] {
  return [
    // Texto principal nas duas superfícies.
    ["tinta/papel", c.tinta, c.papel],
    ["tinta/cartao", c.tinta, c.cartao],

    // Secundário (endereço, metadados) e terciário (dicas).
    ["esmaecido/papel", c.esmaecido, c.papel],
    ["esmaecido/cartao", c.esmaecido, c.cartao],
    ["dica/papel", c.dica, c.papel],
    ["dica/cartao", c.dica, c.cartao],

    // Cores de estado como TEXTO sobre superfície neutra...
    ["marca/cartao", c.marca, c.cartao],
    ["marca/papel", c.marca, c.papel],
    ["ambar/cartao", c.ambar, c.cartao],
    ["ambar/papel", c.ambar, c.papel],
    ["perigo/cartao", c.perigo, c.cartao],
    ["perigo/papel", c.perigo, c.papel],
    ["info/cartao", c.info, c.cartao],
    ["info/papel", c.info, c.papel],

    // ...e sobre o próprio fundo tingido (selos de estado, banners). Este é o
    // par que o B7 errou: cor de texto e fundo tingido escurecem juntos.
    ["marca/marcaSuave", c.marca, c.marcaSuave],
    ["ambar/ambarSuave", c.ambar, c.ambarSuave],
    ["perigo/perigoSuave", c.perigo, c.perigoSuave],
    ["info/infoSuave", c.info, c.infoSuave],
    ["esmaecido/neutroSuave", c.esmaecido, c.neutroSuave],

    // Texto principal e secundário sobre fundo tingido (cabeçalho da tela de
    // finalizar viagem, banners de conflito e de confirmação).
    ["tinta/marcaSuave", c.tinta, c.marcaSuave],
    ["tinta/ambarSuave", c.tinta, c.ambarSuave],
    ["tinta/perigoSuave", c.tinta, c.perigoSuave],
    ["tinta/infoSuave", c.tinta, c.infoSuave],
    ["esmaecido/ambarSuave", c.esmaecido, c.ambarSuave],
    ["esmaecido/perigoSuave", c.esmaecido, c.perigoSuave],

    // Superfícies preenchidas carregam o próprio primeiro plano. Estes dois
    // pares são a razão de `sobreMarca`/`sobrePerigo` existirem: no escuro o
    // preenchimento verde clareia e um "#fff" fixo reprovaria.
    ["sobreMarca/marca (botão primário)", c.sobreMarca, c.marca],
    ["sobrePerigo/perigoForte (botão destrutivo)", c.sobrePerigo, c.perigoForte],

    // Barra invertida do undo de checkin.
    ["sobreInverso/inverso", c.sobreInverso, c.inverso],
    ["destaqueInverso/inverso", c.destaqueInverso, c.inverso],
  ];
}

/**
 * Bordas que DELIMITAM um alvo de toque — 3:1 pelo WCAG 1.4.11.
 *
 * Só `bordaAcao` entra. O botão secundário é `cartao` sobre `papel`, e essas
 * duas superfícies diferem por ~1,07:1 — ou seja, é a borda, e nada mais, que
 * diz onde o botão começa e termina. `linha`/`linha2` ficam fora de propósito:
 * decoram cartão que já se distingue pelo preenchimento, e exigir 3:1 delas
 * desenharia uma moldura suja em volta de cada linha da lista.
 */
function paresDeBorda(c: Paleta): [string, string, string][] {
  return [
    ["bordaAcao/cartao (contorno do botão secundário)", c.bordaAcao, c.cartao],
    ["bordaAcao/papel", c.bordaAcao, c.papel],
  ];
}

/**
 * Guarda de sanidade das bordas tingidas dos selos — **não é nível WCAG**.
 *
 * Elas são decoração sobre um preenchimento que já carrega o estado (fundo
 * tingido + texto colorido, os dois já medidos acima em `paresDeTexto`). O que
 * este limiar pega é o erro bobo: alguém colar o mesmo valor na borda e no
 * fundo, e a borda desaparecer sem ninguém notar.
 */
const BORDA_PERCEPTIVEL = 1.2;

function paresDeBordaTingida(c: Paleta): [string, string, string][] {
  return [
    ["marcaBorda/marcaSuave", c.marcaBorda, c.marcaSuave],
    ["ambarBorda/ambarSuave", c.ambarBorda, c.ambarSuave],
    ["perigoBorda/perigoSuave", c.perigoBorda, c.perigoSuave],
    ["infoBorda/infoSuave", c.infoBorda, c.infoSuave],
  ];
}

describe.each([
  ["clara", paletaClara],
  ["escura", paletaEscura],
])("paleta %s", (_nome, paleta) => {
  it.each(paresDeTexto(paleta))("%s passa AA para texto normal", (_rotulo, frente, fundo) => {
    expect(razaoContraste(frente, fundo)).toBeGreaterThanOrEqual(AA_TEXTO_NORMAL);
  });

  it.each(paresDeBorda(paleta))("%s passa 3:1 (borda de componente)", (_rotulo, frente, fundo) => {
    expect(razaoContraste(frente, fundo)).toBeGreaterThanOrEqual(AA_TEXTO_GRANDE);
  });

  it.each(paresDeBordaTingida(paleta))("%s continua perceptível", (_rotulo, frente, fundo) => {
    expect(razaoContraste(frente, fundo)).toBeGreaterThanOrEqual(BORDA_PERCEPTIVEL);
  });

  // Sem isto, uma paleta poderia "passar" achatando tudo para preto no branco.
  it("mantém as famílias de estado distinguíveis entre si", () => {
    const familias = [paleta.marca, paleta.ambar, paleta.perigo, paleta.info];
    for (let i = 0; i < familias.length; i += 1) {
      for (let j = i + 1; j < familias.length; j += 1) {
        expect(razaoContraste(familias[i], familias[j])).toBeLessThan(AA_TEXTO_NORMAL);
      }
    }
  });
});

describe("funções de contraste", () => {
  it("dá 21:1 entre preto e branco", () => {
    expect(razaoContraste("#000000", "#ffffff")).toBeCloseTo(21, 1);
  });

  it("é simétrica", () => {
    expect(razaoContraste("#0f6e56", "#ffffff")).toBeCloseTo(razaoContraste("#ffffff", "#0f6e56"), 10);
  });

  it("dá 1:1 para a mesma cor, inclusive na forma curta", () => {
    expect(razaoContraste("#fff", "#ffffff")).toBeCloseTo(1, 10);
  });
});
