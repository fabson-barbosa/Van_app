/**
 * Retorno de ação: som + vibração num único ponto de chamada (Bloco B8).
 *
 * Antes cada tela chamava `hapticoAcao()` solto. Com o som entrando, dois canais
 * separados nos mesmos ~15 pontos de chamada garantiriam que um dia um deles
 * ficaria para trás num toque novo. Aqui a semântica é a unidade: a tela diz
 * *o que aconteceu*, não *como avisar*.
 *
 * O vocabulário é o da máquina de estados, não o da UI:
 *
 * | Função | Quando | Som |
 * |---|---|---|
 * | `feedbackAceito` | Cheguei confirmado, Checkin — avançou na rota | sobe |
 * | `feedbackConcluido` | Checkout, Ausente, Finalizar — estado TERMINAL | desce e resolve |
 * | `feedbackDesfeito` | Desfazer checkin, desfazer chegada | glissando descendente |
 * | `feedbackErro` | 409, bloqueio §7.2, falha de rede definitiva | dissonância |
 *
 * **`feedbackSincronizado` não tem som, e isso é deliberado.** Sincronização
 * acontece quando o sinal volta — pode ser minutos depois do toque, com a van
 * em movimento e o motorista sem nenhum contexto do que estaria confirmando. Som
 * só faz sentido amarrado a um comando que ele acabou de dar; fora disso vira
 * ruído aleatório, e ruído aleatório é o que faz o motorista desligar o recurso
 * inteiro. A fila já se anuncia visualmente pelo `PillSync`.
 */
import { hapticoAcao, hapticoErro, hapticoSucesso } from "./haptico";
import { tocar } from "./som";

export { CHAVE_SOM, assinarSom, carregarPreferenciaSom, definirSom, somLigado } from "./som";

/** Comando registrado e a rota avançou: Cheguei, Checkin. */
export function feedbackAceito(): void {
  hapticoAcao();
  tocar("aceito");
}

/** Estado terminal alcançado: Checkout, Marcar ausente, Finalizar viagem. */
export function feedbackConcluido(): void {
  hapticoAcao();
  tocar("concluido");
}

/** Reversão: desfazer checkin, desfazer chegada. */
export function feedbackDesfeito(): void {
  hapticoAcao();
  tocar("desfeito");
}

/** Recusa: 409 de domínio, bloqueio do §7.2, falha definitiva. */
export function feedbackErro(): void {
  hapticoErro();
  tocar("erro");
}

/** Fila drenou com sucesso. Sem som — ver docstring do módulo. */
export function feedbackSincronizado(): void {
  hapticoSucesso();
}
