import React from "react";
import TestRenderer, { act } from "react-test-renderer";

import { MenuAcoesAluno, temAcoesForaDeOrdem } from "../MenuAcoesAluno";
import type { TripStudentEstado } from "../../../shared/api/types";

function renderizar(estado: TripStudentEstado) {
  const onDesfazerChegada = jest.fn();
  const onMarcarAusente = jest.fn();
  const onFechar = jest.fn();
  let arvore!: TestRenderer.ReactTestRenderer;

  act(() => {
    arvore = TestRenderer.create(
      <MenuAcoesAluno
        visivel
        nomeAluno="Ana Silva"
        estado={estado}
        onDesfazerChegada={onDesfazerChegada}
        onMarcarAusente={onMarcarAusente}
        onFechar={onFechar}
      />
    );
  });

  const tem = (testID: string) => arvore.root.findAll((n) => n.props?.testID === testID).length > 0;
  return { arvore, tem, onDesfazerChegada, onMarcarAusente };
}

describe("temAcoesForaDeOrdem", () => {
  // O badge só vira alvo de toque onde há algo a fazer. `a_bordo` fica de fora
  // porque desfazer checkin tem janela de 60s e caminho próprio (a barra de
  // undo); os terminais, porque sair de `entregue`/`ausente` não existe na
  // máquina de estados.
  it("libera o badge só em aguardando e chegou", () => {
    expect(temAcoesForaDeOrdem("aguardando")).toBe(true);
    expect(temAcoesForaDeOrdem("chegou")).toBe(true);
    expect(temAcoesForaDeOrdem("a_bordo")).toBe(false);
    expect(temAcoesForaDeOrdem("entregue")).toBe(false);
    expect(temAcoesForaDeOrdem("ausente")).toBe(false);
  });
});

describe("ações oferecidas por estado", () => {
  it("em 'aguardando' oferece só marcar ausente", () => {
    const { tem } = renderizar("aguardando");
    expect(tem("acao-marcar-ausente")).toBe(true);
    expect(tem("acao-desfazer-chegada")).toBe(false);
  });

  // Esta é a saída que não existia: o motorista apertou Cheguei no aluno
  // errado, o push já saiu, e o §7.2 bloqueia o Cheguei seguinte enquanto a
  // parada anterior estiver em `chegou`. Sem isto ele ficava preso entre um
  // Checkin falso e um Ausente permanente.
  it("em 'chegou' oferece desfazer chegada e marcar ausente", () => {
    const { tem } = renderizar("chegou");
    expect(tem("acao-desfazer-chegada")).toBe(true);
    expect(tem("acao-marcar-ausente")).toBe(true);
  });
});
