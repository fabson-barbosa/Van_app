/**
 * Undos de Checkin pendentes — janela de 30s na UI (CLAUDE.md §8).
 *
 * Estado de MÓDULO, não `useState` de tela, e isso é o ponto do arquivo.
 * Antes do B7 o undo vivia num `useState` da `ViagemScreen`, o que quebrava a
 * promessa do contador de três jeitos:
 *
 * 1. **Sumia ao navegar.** `useViagemStore` é um hook com estado próprio por
 *    montagem — ir até "Finalizar viagem" e voltar destruía o undo antes dos
 *    30s. A barra prometia um prazo que a tela não sustentava.
 * 2. **Só cabia um.** Era um slot único: dois irmãos na mesma parada (o modelo
 *    permite vários alunos por parada) e o undo do primeiro era sobrescrito
 *    sem aviso, ainda dentro da janela.
 * 3. **O relógio reiniciava.** O contador era um `useState` que voltava a 30 a
 *    cada remontagem do componente.
 *
 * Guardar `expiraEm` como instante absoluto resolve o (3) de graça: quem
 * renderiza deriva o restante de `Date.now()`, então remontar não devolve tempo
 * que já passou.
 *
 * A janela do SERVIDOR é 60s (`JANELA_DESFAZER_CHECKIN_SEGUNDOS`), medida
 * contra o relógio dele. Os 30s daqui são deliberadamente menores: dão folga
 * para latência e fila offline, e não incentivam o motorista a "corrigir" um
 * checkin depois de a van já ter saído do lugar.
 */
export const DURACAO_UNDO_SEGUNDOS = 30;

export interface UndoCheckin {
  viagemId: string;
  tripStudentId: string;
  nomeAluno: string;
  /** `eventId` do Checkin — chave de idempotência e o que permite cancelar o
   * item na fila offline antes de ele sair (ver `ViagemStore.desfazerCheckin`). */
  eventId: string;
  /** Instante absoluto (ms) em que a oferta de desfazer expira. */
  expiraEm: number;
}

type Ouvinte = () => void;

let pendentes: UndoCheckin[] = [];
const ouvintes = new Set<Ouvinte>();

function emitir(): void {
  ouvintes.forEach((ouvinte) => ouvinte());
}

export function assinarUndos(ouvinte: Ouvinte): () => void {
  ouvintes.add(ouvinte);
  return () => {
    ouvintes.delete(ouvinte);
  };
}

export function registrarUndo(
  entrada: Omit<UndoCheckin, "expiraEm">,
  agoraMs: number = Date.now()
): void {
  pendentes = [
    ...pendentes.filter((u) => u.eventId !== entrada.eventId),
    { ...entrada, expiraEm: agoraMs + DURACAO_UNDO_SEGUNDOS * 1000 },
  ];
  emitir();
}

export function descartarUndo(eventId: string): void {
  const antes = pendentes.length;
  pendentes = pendentes.filter((u) => u.eventId !== eventId);
  if (pendentes.length !== antes) emitir();
}

/** Remove os já vencidos e devolve os vivos da viagem, do mais antigo para o
 * mais novo. Chamado na renderização — a limpeza acontece por leitura, sem
 * precisar de timer global. */
export function listarUndosVivos(viagemId: string, agoraMs: number = Date.now()): UndoCheckin[] {
  const vivos = pendentes.filter((u) => u.expiraEm > agoraMs);
  if (vivos.length !== pendentes.length) {
    pendentes = vivos;
    // Sem emitir: esta função roda DURANTE a renderização de quem assina, e
    // notificar aqui provocaria um laço de atualização.
  }
  return vivos.filter((u) => u.viagemId === viagemId).sort((a, b) => a.expiraEm - b.expiraEm);
}

/** Só para testes — o estado é global por natureza. */
export function limparUndosParaTeste(): void {
  pendentes = [];
  ouvintes.clear();
}
