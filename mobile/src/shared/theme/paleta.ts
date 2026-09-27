/**
 * Paletas clara e escura (Bloco B8).
 *
 * A identidade é a mesma de sempre — papel creme, verde da marca, selos
 * coloridos por estado. O que mudou: os nomes agora descrevem PAPÉIS, não
 * valores, e existem duas realizações. `cores.tinta` quer dizer "a cor do texto
 * principal", que é quase preta no claro e quase branca no escuro. Nenhum
 * componente pode assumir "tinta é escuro".
 *
 * Três regras que este arquivo impõe:
 *
 * 1. **Todo fundo é opaco.** Antes, `linha` era `rgba(16,35,30,0.10)` e servia
 *    de fundo do selo "Aguardando". Cor translúcida não tem razão de contraste
 *    — ela depende do que está atrás — então era impossível provar AA. Agora
 *    cada fundo tem valor próprio por paleta. `overlay` é a única exceção, e é
 *    de propósito (véu do diálogo, não carrega texto).
 * 2. **Superfície preenchida carrega o próprio primeiro plano.** `sobreMarca` e
 *    `sobrePerigo` existem porque o botão primário inverte entre as paletas: no
 *    claro é verde escuro com texto branco; no escuro, verde claro com texto
 *    quase preto. Um `"#ffffff"` fixo no componente reprovaria AA no escuro.
 * 3. **O escuro não é preto.** `papel: #101614`, não `#000`. Preto puro com
 *    texto branco num aparelho no painel, de noite, é ofuscante — e em OLED o
 *    texto claro sobre preto absoluto floresce (halação). Cinza-grafite com
 *    traço de verde mantém a identidade e cansa menos.
 *
 * Os valores estão travados por `__tests__/contraste.test.ts`: todo par
 * texto/fundo das DUAS paletas é medido contra AA a cada `npm test`. Mexer numa
 * cor sem refazer a conta quebra o build, não a viagem do motorista.
 */

export type NomeModo = "claro" | "escuro";

export interface Paleta {
  /** Identificador da paleta — usado para memoizar folhas de estilo. */
  readonly nome: NomeModo;

  /** Texto principal. Quase preto no claro, quase branco no escuro. */
  readonly tinta: string;
  /** Fundo da tela. */
  readonly papel: string;
  /** Fundo de cartão/linha — um passo à frente de `papel`. */
  readonly cartao: string;
  /** Divisória sutil. Decorativa: separa itens que já se distinguem pelo fundo. */
  readonly linha: string;
  /** Borda de cartão — mais presente que `linha`, ainda decorativa. */
  readonly linha2: string;
  /**
   * Borda que IDENTIFICA um alvo de toque, não decora: o contorno do botão
   * secundário. Existe separada de `linha2` porque o WCAG 1.4.11 pede 3:1 de
   * quem delimita componente, e `linha2` num cartão inteiro nessa força
   * desenharia uma moldura suja em volta de cada linha da lista.
   */
  readonly bordaAcao: string;
  /** Texto secundário: endereço, metadados. */
  readonly esmaecido: string;
  /** Texto terciário: dicas, rótulos auxiliares. */
  readonly dica: string;

  /** Verde da marca: ação primária, estado a bordo/entregue. */
  readonly marca: string;
  /** Verde de realce (progresso, acentos finos). */
  readonly marca2: string;
  /** Fundo do selo/banner verde. */
  readonly marcaSuave: string;
  /** Borda do selo/banner verde. */
  readonly marcaBorda: string;
  /** Texto sobre preenchimento `marca`. */
  readonly sobreMarca: string;

  /** Âmbar: ausente, atraso, pendente de sincronização. */
  readonly ambar: string;
  readonly ambarSuave: string;
  readonly ambarBorda: string;

  /** Vermelho: erro, conflito, bloqueio. */
  readonly perigo: string;
  readonly perigoSuave: string;
  readonly perigoBorda: string;
  /** Preenchimento sólido de confirmação irreversível (CLAUDE.md §6.2). */
  readonly perigoForte: string;
  /** Texto sobre preenchimento `perigoForte`. */
  readonly sobrePerigo: string;

  /** Azul: estado "chegou", ações informativas. */
  readonly info: string;
  readonly infoSuave: string;
  readonly infoBorda: string;

  /** Fundo do selo neutro ("Aguardando"). */
  readonly neutroSuave: string;

  /** Barra invertida (undo de checkin) — contrasta com o resto da tela. */
  readonly inverso: string;
  readonly sobreInverso: string;
  /** Ação dentro da barra invertida. */
  readonly destaqueInverso: string;

  /** Véu do diálogo. Único valor translúcido; não carrega texto. */
  readonly overlay: string;
}

export const paletaClara: Paleta = {
  nome: "claro",

  tinta: "#10231e",
  papel: "#f4f1ea",
  cartao: "#ffffff",
  linha: "#e2ddd1",
  linha2: "#cdc6b6",
  bordaAcao: "#8a8578",
  /** 7,07:1 sobre `cartao`, 6,42:1 sobre `papel`. */
  esmaecido: "#4d5b55",
  /** 5,19:1 sobre `cartao`, 4,61:1 sobre `papel`. O valor "natural" (#68756f)
   * dava 4,27:1 sobre o creme — reprovava exatamente na superfície mais usada. */
  dica: "#616d67",

  /** 5,79:1 sobre `cartao`; 5,18:1 sobre `marcaSuave`. */
  marca: "#0f6e56",
  marca2: "#1d9e75",
  marcaSuave: "#e1f5ee",
  marcaBorda: "#b3ded0",
  sobreMarca: "#ffffff",

  /** 6,27:1 sobre `cartao`; 5,46:1 sobre `ambarSuave`. */
  ambar: "#8a5410",
  ambarSuave: "#faeeda",
  ambarBorda: "#e8d5b4",

  perigo: "#a32d2d",
  perigoSuave: "#fceaea",
  perigoBorda: "#f0cbcb",
  perigoForte: "#a32d2d",
  sobrePerigo: "#ffffff",

  info: "#185fa5",
  infoSuave: "#e6f1fb",
  infoBorda: "#c2d9f1",

  neutroSuave: "#e8e4da",

  inverso: "#10231e",
  sobreInverso: "#ffffff",
  destaqueInverso: "#efb742",

  overlay: "rgba(16,35,30,0.55)",
};

export const paletaEscura: Paleta = {
  nome: "escuro",

  tinta: "#e9efec",
  papel: "#101614",
  cartao: "#1b2321",
  linha: "#2b3532",
  linha2: "#3d4844",
  bordaAcao: "#647570",
  /** 7,26:1 sobre `cartao`. */
  esmaecido: "#a6b2ac",
  /** 5,74:1 sobre `cartao` — mais folga que no claro de propósito: de noite a
   * pupila está dilatada e texto cinza em fundo escuro "some" antes. */
  dica: "#94a09a",

  /** Verde CLARO aqui: o #0f6e56 do modo claro dá 1,7:1 sobre `cartao` e
   * seria ilegível. 8,05:1 sobre `cartao`. */
  marca: "#4ecfa0",
  marca2: "#67dcb1",
  marcaSuave: "#152e28",
  marcaBorda: "#28564a",
  /** Texto quase preto sobre o preenchimento verde claro — 9,80:1. Inverte em
   * relação ao modo claro, e é por isso que este token existe. */
  sobreMarca: "#04160f",

  ambar: "#e4ad4e",
  ambarSuave: "#2c2315",
  ambarBorda: "#4d3d20",

  perigo: "#f4938d",
  perigoSuave: "#30191a",
  perigoBorda: "#57292a",
  /** Mais claro que o do modo claro: um vermelho escuro sobre fundo escuro
   * perde a força de "irreversível" que o §6.2 pede do botão. */
  perigoForte: "#bf3f3c",
  sobrePerigo: "#ffffff",

  info: "#7dbaf2",
  infoSuave: "#14243a",
  infoBorda: "#2b4a70",

  neutroSuave: "#252f2c",

  /** No claro a barra de undo é escura sobre tela clara. No escuro ela NÃO
   * vira clara: uma barra branca no painel, de noite, ofusca. É uma superfície
   * elevada, que se distingue por altura e não por inversão de luminância. */
  inverso: "#2d3b37",
  sobreInverso: "#eef3f1",
  destaqueInverso: "#f2c667",

  overlay: "rgba(0,0,0,0.66)",
};

export const paletas: Record<NomeModo, Paleta> = {
  claro: paletaClara,
  escuro: paletaEscura,
};

/**
 * Paleta estática = a clara.
 *
 * Mantida porque as telas do Responsável e o Login importam `cores` direto e
 * NÃO entraram no escopo do B8 (decisão do usuário: reconstruir só o
 * Motorista). Elas continuam renderizando exatamente como antes, sem
 * `TemaProvider` por cima. Código novo do Motorista usa `useTema()`.
 */
export const cores = paletaClara;
