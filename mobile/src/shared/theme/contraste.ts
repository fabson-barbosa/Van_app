/**
 * Razão de contraste WCAG 2.1 (Bloco B8).
 *
 * Existe como código de produção, e não só dentro do teste, porque o CLAUDE.md
 * §8 exige contraste AA — a tela é lida sob sol direto, em aparelho antigo. Com
 * duas paletas (clara e escura) isso deixou de ser verificável no olho: uma cor
 * que passa sobre creme pode reprovar sobre grafite, e o erro é invisível para
 * quem desenvolve num monitor bom, em escritório.
 *
 * O B7 ajustou cores "para passar em AA" medindo à mão e anotando os valores num
 * documento. Documento não reprova build. `tests/contraste.test.ts` usa estas
 * funções para travar todos os pares de texto/fundo das duas paletas.
 */

/** AA para texto normal (< 18pt / < 14pt negrito). */
export const AA_TEXTO_NORMAL = 4.5;

/** AA para texto grande (≥ 18pt, ou ≥ 14pt negrito) e para componentes de UI. */
export const AA_TEXTO_GRANDE = 3;

export interface Rgb {
  r: number;
  g: number;
  b: number;
}

/**
 * Aceita `#rgb`, `#rrggbb` e `rgba(r,g,b,a)`. O alfa de `rgba()` é ignorado de
 * propósito: quem precisa medir uma cor translúcida tem que compor com o fundo
 * primeiro (`compor`), porque a razão só faz sentido entre cores opacas.
 */
export function paraRgb(cor: string): Rgb {
  const texto = cor.trim();

  if (texto.startsWith("#")) {
    const hex = texto.slice(1);
    if (hex.length === 3) {
      return {
        r: parseInt(hex[0] + hex[0], 16),
        g: parseInt(hex[1] + hex[1], 16),
        b: parseInt(hex[2] + hex[2], 16),
      };
    }
    if (hex.length === 6) {
      return {
        r: parseInt(hex.slice(0, 2), 16),
        g: parseInt(hex.slice(2, 4), 16),
        b: parseInt(hex.slice(4, 6), 16),
      };
    }
    throw new Error(`Hex não suportado: ${cor}`);
  }

  const rgba = texto.match(/^rgba?\(([^)]+)\)$/);
  if (rgba) {
    const partes = rgba[1].split(",").map((p) => Number(p.trim()));
    if (partes.length < 3 || partes.some((n) => Number.isNaN(n))) {
      throw new Error(`rgb()/rgba() inválido: ${cor}`);
    }
    return { r: partes[0], g: partes[1], b: partes[2] };
  }

  throw new Error(`Formato de cor não suportado: ${cor}`);
}

/** Alfa-composição de `frente` sobre `fundo` — os dois opacos no resultado. */
export function compor(frente: string, alfa: number, fundo: string): Rgb {
  const f = paraRgb(frente);
  const t = paraRgb(fundo);
  return {
    r: Math.round(f.r * alfa + t.r * (1 - alfa)),
    g: Math.round(f.g * alfa + t.g * (1 - alfa)),
    b: Math.round(f.b * alfa + t.b * (1 - alfa)),
  };
}

function canal(valor: number): number {
  const s = valor / 255;
  return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
}

/** Luminância relativa (WCAG 2.1). */
export function luminancia(cor: string | Rgb): number {
  const { r, g, b } = typeof cor === "string" ? paraRgb(cor) : cor;
  return 0.2126 * canal(r) + 0.7152 * canal(g) + 0.0722 * canal(b);
}

/** Razão de contraste entre duas cores opacas — de 1 (igual) a 21 (preto/branco). */
export function razaoContraste(a: string | Rgb, b: string | Rgb): number {
  const la = luminancia(a);
  const lb = luminancia(b);
  const claro = Math.max(la, lb);
  const escuro = Math.min(la, lb);
  return (claro + 0.05) / (escuro + 0.05);
}
