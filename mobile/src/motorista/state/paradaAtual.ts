/**
 * Seleção da "parada atual" — o aluno cuja ação o card do rodapé oferece
 * (Bloco B7). Lógica pura, sem React e sem rede, para ser testável.
 *
 * ## Por que não é simplesmente "o primeiro não-terminal"
 *
 * Uma rota matinal tem DUAS fases, e elas não se intercalam:
 *
 * 1. **Embarque** — os alunos sobem um a um, na ordem das paradas:
 *    `aguardando` -> `chegou` -> `a_bordo`.
 * 2. **Desembarque** — chegando na escola, todo mundo que está `a_bordo` desce:
 *    `a_bordo` -> `entregue`.
 *
 * Depois que o aluno 1 embarca, ele fica `a_bordo` pela rota inteira. "Primeiro
 * não-terminal por ordem" apontaria para ele — e o card ofereceria **Checkout**
 * enquanto a van ainda está indo buscar o aluno 3. Ação errada, no meio do
 * trânsito, com confirmação destrutiva do lado.
 *
 * A regra correta é por FASE: enquanto existir alguém em `aguardando` ou
 * `chegou`, a viagem está embarcando e o alvo é o primeiro deles. Só quando não
 * sobra ninguém pra pegar é que a viagem passa a desembarcar, e aí o alvo é o
 * primeiro `a_bordo`.
 *
 * Isso também vale para o aluno pulado: marcar ausente alguém em `aguardando`
 * simplesmente o tira da fila de embarque e o alvo anda pro próximo.
 */
import type { TripStudentEstado, TripStudentOut } from "../../shared/api/types";

export type FaseViagem = "embarque" | "desembarque";

export interface ParadaAtual {
  alvo: TripStudentOut;
  fase: FaseViagem;
}

const TERMINAIS: readonly TripStudentEstado[] = ["entregue", "ausente"];

export function ehTerminal(estado: TripStudentEstado): boolean {
  return TERMINAIS.includes(estado);
}

function porOrdem(a: TripStudentOut, b: TripStudentOut): number {
  return a.ordem - b.ordem;
}

/**
 * `null` quando todos os alunos já estão em estado terminal — a viagem está
 * pronta para ser finalizada e o card some da tela.
 */
export function selecionarParadaAtual(tripStudents: readonly TripStudentOut[]): ParadaAtual | null {
  const ordenados = [...tripStudents].sort(porOrdem);

  const embarcando = ordenados.find((ts) => ts.estado === "aguardando" || ts.estado === "chegou");
  if (embarcando) return { alvo: embarcando, fase: "embarque" };

  const desembarcando = ordenados.find((ts) => ts.estado === "a_bordo");
  if (desembarcando) return { alvo: desembarcando, fase: "desembarque" };

  return null;
}

/**
 * Quantos alunos ainda exigem alguma ação do motorista.
 *
 * Substitui o contador antigo, que exibia `a_bordo + entregue` sob o rótulo
 * "concluídos" — mentindo duas vezes: a tela de finalizar trata `a_bordo` como
 * alerta duro (§7.1), e ausentes não entravam na conta, então uma rota com duas
 * faltas travava em "10 / 12" e fechava o turno parecendo inacabada.
 */
export function contarRestantes(tripStudents: readonly TripStudentOut[]): number {
  return tripStudents.filter((ts) => !ehTerminal(ts.estado)).length;
}

/** Rótulo do atraso acumulado da viagem (CLAUDE.md §5). O dado já vinha no
 * `ViagemOut` desde o B3 e nenhuma tela do motorista o exibia — ele descobria
 * que estava atrasado quando um responsável ligava.
 *
 * Faixa de minutos, nunca segundo exato: sem GPS, precisão falsa destrói a
 * confiança (§5). Abaixo de 2min é ruído de arredondamento das estimativas. */
export function rotuloAtraso(atrasoSegundos: number): string | null {
  const minutos = Math.round(atrasoSegundos / 60);
  if (minutos >= 2) return `~${minutos} min atrasado`;
  if (minutos <= -2) return `~${Math.abs(minutos)} min adiantado`;
  return null;
}

/** Cronômetro de espera na parada — "há quanto tempo estou parado nesta casa".
 * O responsável vê esse número desde o B5 (notificação persistente, §5); quem
 * está de fato esperando na porta, não via. */
export function formatarEspera(chegouEmISO: string, agoraMs: number): string {
  const decorridoMs = agoraMs - new Date(chegouEmISO).getTime();
  const totalSegundos = Math.max(0, Math.floor(decorridoMs / 1000));
  const minutos = Math.floor(totalSegundos / 60);
  const segundos = totalSegundos % 60;
  if (minutos === 0) return `esperando há ${segundos}s`;
  return `esperando há ${minutos}min${String(segundos).padStart(2, "0")}`;
}
