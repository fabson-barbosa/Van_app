/**
 * Ponto único do sistema de design (Bloco B8).
 *
 * Era `src/shared/theme.ts` (um arquivo). Virou diretório com `index.ts` de
 * propósito: todos os ~20 `import { cores } from "../theme"` que já existiam
 * continuam resolvendo, então as telas fora do escopo do B8 (Responsável,
 * Login) não precisaram ser tocadas.
 */
export { AA_TEXTO_GRANDE, AA_TEXTO_NORMAL, compor, luminancia, paraRgb, razaoContraste } from "./contraste";
export { type NomeModo, type Paleta, cores, paletaClara, paletaEscura, paletas } from "./paleta";
export {
  BarraStatusDoTema,
  CHAVE_MODO,
  type ModoTema,
  TemaClaroFixo,
  TemaProvider,
  comTemaClaro,
  ehModoValido,
  resolverPaleta,
  useTema,
} from "./TemaContext";
export { ESPACO_LETRA_SELO, TOQUE_GRANDE, TOQUE_MIN, espacamento, peso, raio, tipografia } from "./tokens";
export { estilosPara, useEstilos } from "./useEstilos";
