import {
  contarRestantes,
  formatarEspera,
  rotuloAtraso,
  selecionarParadaAtual,
} from "../paradaAtual";
import type { TripStudentEstado, TripStudentOut } from "../../../shared/api/types";

function aluno(ordem: number, estado: TripStudentEstado, extra: Partial<TripStudentOut> = {}): TripStudentOut {
  return {
    id: `ts-${ordem}`,
    viagem_id: "v1",
    aluno_id: `a-${ordem}`,
    parada_id: `p-${ordem}`,
    ordem,
    estado,
    chegou_em: null,
    checkin_em: null,
    checkout_em: null,
    ausente_em: null,
    aluno_nome: `Aluno ${ordem}`,
    parada_endereco: `Rua ${ordem}`,
    ...extra,
  };
}

describe("selecionarParadaAtual", () => {
  it("na fase de embarque aponta o primeiro aluno por pegar", () => {
    const atual = selecionarParadaAtual([aluno(1, "aguardando"), aluno(2, "aguardando")]);
    expect(atual?.alvo.ordem).toBe(1);
    expect(atual?.fase).toBe("embarque");
  });

  it("ignora a ordem da lista e usa a ordem da parada", () => {
    const atual = selecionarParadaAtual([aluno(3, "aguardando"), aluno(1, "aguardando")]);
    expect(atual?.alvo.ordem).toBe(1);
  });

  it("prefere quem já está 'chegou' se ele vier antes", () => {
    const atual = selecionarParadaAtual([aluno(1, "chegou"), aluno(2, "aguardando")]);
    expect(atual?.alvo.ordem).toBe(1);
    expect(atual?.fase).toBe("embarque");
  });

  // O ponto do módulo: quem já embarcou fica `a_bordo` pela rota inteira. Se a
  // regra fosse "primeiro não-terminal", o card ofereceria CHECKOUT do aluno 1
  // enquanto a van ainda vai buscar o aluno 2 — ação errada, com confirmação
  // destrutiva do lado, no meio do trânsito.
  it("não oferece checkout enquanto ainda houver aluno para pegar", () => {
    const atual = selecionarParadaAtual([aluno(1, "a_bordo"), aluno(2, "aguardando")]);
    expect(atual?.alvo.ordem).toBe(2);
    expect(atual?.fase).toBe("embarque");
  });

  it("só entra na fase de desembarque quando ninguém mais falta pegar", () => {
    const atual = selecionarParadaAtual([
      aluno(1, "a_bordo"),
      aluno(2, "a_bordo"),
      aluno(3, "ausente"),
    ]);
    expect(atual?.alvo.ordem).toBe(1);
    expect(atual?.fase).toBe("desembarque");
  });

  it("marcar ausente um aluno em espera passa o alvo adiante", () => {
    const atual = selecionarParadaAtual([aluno(1, "ausente"), aluno(2, "aguardando")]);
    expect(atual?.alvo.ordem).toBe(2);
  });

  it("devolve null com todos terminais — o card some e a viagem pode fechar", () => {
    expect(selecionarParadaAtual([aluno(1, "entregue"), aluno(2, "ausente")])).toBeNull();
  });

  it("devolve null para viagem sem alunos", () => {
    expect(selecionarParadaAtual([])).toBeNull();
  });
});

describe("contarRestantes", () => {
  it("conta apenas quem ainda exige ação", () => {
    expect(
      contarRestantes([aluno(1, "entregue"), aluno(2, "a_bordo"), aluno(3, "aguardando")])
    ).toBe(2);
  });

  // O contador antigo somava `a_bordo + entregue` sob o rótulo "concluídos":
  // dizia "concluído" para um aluno que a tela de finalizar trata como alerta
  // duro (§7.1).
  it("não trata quem está a bordo como resolvido", () => {
    expect(contarRestantes([aluno(1, "a_bordo")])).toBe(1);
  });

  // E ausentes não entravam na conta, então uma rota com duas faltas travava em
  // "10 / 12" e fechava o turno parecendo inacabada.
  it("trata ausente como resolvido — o turno fecha zerado", () => {
    expect(contarRestantes([aluno(1, "entregue"), aluno(2, "ausente")])).toBe(0);
  });
});

describe("rotuloAtraso", () => {
  it("silencia ruído de arredondamento perto do horário", () => {
    expect(rotuloAtraso(0)).toBeNull();
    expect(rotuloAtraso(60)).toBeNull();
    expect(rotuloAtraso(-60)).toBeNull();
  });

  it("informa atraso e adiantamento em minutos", () => {
    expect(rotuloAtraso(8 * 60)).toBe("~8 min atrasado");
    expect(rotuloAtraso(-5 * 60)).toBe("~5 min adiantado");
  });
});

describe("formatarEspera", () => {
  const base = new Date("2026-07-28T07:00:00.000Z");

  it("mostra só segundos no primeiro minuto", () => {
    expect(formatarEspera(base.toISOString(), base.getTime() + 42_000)).toBe("esperando há 42s");
  });

  it("mostra minutos e segundos depois disso", () => {
    expect(formatarEspera(base.toISOString(), base.getTime() + 80_000)).toBe("esperando há 1min20");
  });

  it("nunca fica negativo com relógio do aparelho atrás do servidor", () => {
    expect(formatarEspera(base.toISOString(), base.getTime() - 5_000)).toBe("esperando há 0s");
  });
});
