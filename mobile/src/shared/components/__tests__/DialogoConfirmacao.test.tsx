import React from "react";
import TestRenderer, { act } from "react-test-renderer";

import { DialogoConfirmacao, GUARDA_MS } from "../DialogoConfirmacao";

/**
 * `findByProps({testID})` casa PRIMEIRO com o elemento `Botao56` — e o
 * `onPress` dele é o callback cru, que ignora a guarda. O alvo certo é o
 * `Pressable` que o `Botao56` renderiza: é lá que `desabilitado` vira
 * `onPress: undefined` e `accessibilityState.disabled`.
 */
function alvo(arvore: TestRenderer.ReactTestRenderer, testID: string) {
  const nos = arvore.root.findAll(
    (n) => n.props?.testID === testID && n.props?.accessibilityState !== undefined
  );
  return nos[0];
}

function tocar(arvore: TestRenderer.ReactTestRenderer, testID: string) {
  act(() => {
    alvo(arvore, testID).props.onPress?.();
  });
}

function estaTravado(arvore: TestRenderer.ReactTestRenderer, testID: string): boolean {
  return alvo(arvore, testID).props.accessibilityState.disabled === true;
}

type Props = React.ComponentProps<typeof DialogoConfirmacao>;

function renderizar(props: Partial<Props> = {}) {
  const onConfirmar = jest.fn();
  const onCancelar = jest.fn();
  let arvore!: TestRenderer.ReactTestRenderer;

  act(() => {
    arvore = TestRenderer.create(
      <DialogoConfirmacao
        visivel
        titulo="Ana Silva"
        rotuloConfirmar="Marcar ausente"
        varianteConfirmar="destrutivo"
        onConfirmar={onConfirmar}
        onCancelar={onCancelar}
        {...props}
      />
    );
  });

  return { arvore, onConfirmar, onCancelar };
}

beforeEach(() => {
  jest.useFakeTimers();
});

afterEach(() => {
  jest.useRealTimers();
});

describe("guarda anti-toque-duplo", () => {
  // O risco real não é o toque acidental — é o REFLEXO. Um diálogo que sempre
  // aparece no mesmo lugar vira "toca duas vezes" em três dias, e aí deixou de
  // proteger. Travar os botões por um instante garante que o segundo toque de
  // um toque-duplo não confirme nada.
  it("não confirma enquanto a guarda está ativa", () => {
    const { arvore, onConfirmar } = renderizar();

    expect(estaTravado(arvore, "dialogo-confirmar")).toBe(true);
    tocar(arvore, "dialogo-confirmar");
    expect(onConfirmar).not.toHaveBeenCalled();
  });

  it("confirma depois que a guarda expira", () => {
    const { arvore, onConfirmar } = renderizar();

    act(() => {
      jest.advanceTimersByTime(GUARDA_MS + 10);
    });

    expect(estaTravado(arvore, "dialogo-confirmar")).toBe(false);
    tocar(arvore, "dialogo-confirmar");
    expect(onConfirmar).toHaveBeenCalledTimes(1);
  });

  it("a guarda também segura o Cancelar, para o toque duplo não fechar sozinho", () => {
    const { arvore, onCancelar } = renderizar();

    tocar(arvore, "dialogo-cancelar");
    expect(onCancelar).not.toHaveBeenCalled();

    act(() => {
      jest.advanceTimersByTime(GUARDA_MS + 10);
    });
    tocar(arvore, "dialogo-cancelar");
    expect(onCancelar).toHaveBeenCalledTimes(1);
  });

  // O componente é montado uma vez por tela e reaproveitado a cada aluno — a
  // guarda precisa valer na abertura seguinte, não só na primeira.
  it("a guarda reinicia a cada abertura", () => {
    const onConfirmar = jest.fn();
    const props: Props = {
      visivel: false,
      titulo: "Ana Silva",
      onConfirmar,
      onCancelar: jest.fn(),
    };
    let arvore!: TestRenderer.ReactTestRenderer;

    act(() => {
      arvore = TestRenderer.create(<DialogoConfirmacao {...props} />);
    });

    // Primeira abertura, guarda cumprida.
    act(() => {
      arvore.update(<DialogoConfirmacao {...props} visivel />);
    });
    act(() => {
      jest.advanceTimersByTime(GUARDA_MS + 10);
    });
    expect(estaTravado(arvore, "dialogo-confirmar")).toBe(false);

    // Fecha e reabre para outro aluno.
    act(() => {
      arvore.update(<DialogoConfirmacao {...props} titulo="Bruno Costa" />);
    });
    act(() => {
      arvore.update(<DialogoConfirmacao {...props} titulo="Bruno Costa" visivel />);
    });

    expect(estaTravado(arvore, "dialogo-confirmar")).toBe(true);
    tocar(arvore, "dialogo-confirmar");
    expect(onConfirmar).not.toHaveBeenCalled();
  });
});

describe("anatomia (CLAUDE.md §6)", () => {
  function textosDe(arvore: TestRenderer.ReactTestRenderer): unknown[] {
    return arvore.root.findAllByType("Text" as never).flatMap((n) => n.props.children);
  }

  it("mostra título e subtítulo", () => {
    const { arvore } = renderizar({ subtitulo: "Rua das Flores, 120" });
    expect(textosDe(arvore)).toContain("Ana Silva");
    expect(textosDe(arvore)).toContain("Rua das Flores, 120");
  });

  it("omite o subtítulo quando não há endereço", () => {
    const { arvore } = renderizar({ subtitulo: null });
    const textos = textosDe(arvore);
    expect(textos).toContain("Ana Silva");
    expect(textos).toContain("Marcar ausente");
    expect(textos).toContain("Cancelar");
  });
});
