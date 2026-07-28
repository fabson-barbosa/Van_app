import {
  DURACAO_UNDO_SEGUNDOS,
  descartarUndo,
  limparUndosParaTeste,
  listarUndosVivos,
  registrarUndo,
} from "../undoCheckin";

const T0 = 1_700_000_000_000;

function registrar(eventId: string, nomeAluno: string, agoraMs: number, viagemId = "v1") {
  registrarUndo({ viagemId, tripStudentId: `ts-${eventId}`, nomeAluno, eventId }, agoraMs);
}

beforeEach(() => {
  limparUndosParaTeste();
});

describe("undos de checkin", () => {
  it("registra um undo vivo dentro da janela", () => {
    registrar("e1", "Ana", T0);
    const vivos = listarUndosVivos("v1", T0 + 1_000);
    expect(vivos).toHaveLength(1);
    expect(vivos[0].nomeAluno).toBe("Ana");
    expect(vivos[0].expiraEm).toBe(T0 + DURACAO_UNDO_SEGUNDOS * 1000);
  });

  // O defeito original: o undo era um slot único (`setUndo` sobrescrevia), então
  // dois irmãos na mesma parada — o modelo permite vários alunos por parada —
  // faziam o undo do primeiro sumir sem aviso, ainda dentro dos 30s.
  it("mantém undos independentes para checkins seguidos", () => {
    registrar("e1", "Ana", T0);
    registrar("e2", "Bruno", T0 + 2_000);

    const vivos = listarUndosVivos("v1", T0 + 3_000);
    expect(vivos.map((u) => u.nomeAluno)).toEqual(["Ana", "Bruno"]);
  });

  it("expirar um não afeta o outro", () => {
    registrar("e1", "Ana", T0);
    registrar("e2", "Bruno", T0 + 10_000);

    // 31s depois do primeiro: Ana venceu, Bruno ainda tem 9s.
    const vivos = listarUndosVivos("v1", T0 + 31_000);
    expect(vivos.map((u) => u.nomeAluno)).toEqual(["Bruno"]);
  });

  it("descarta por eventId ao desfazer", () => {
    registrar("e1", "Ana", T0);
    registrar("e2", "Bruno", T0);
    descartarUndo("e1");
    expect(listarUndosVivos("v1", T0 + 1_000).map((u) => u.eventId)).toEqual(["e2"]);
  });

  it("não vaza undos entre viagens", () => {
    registrar("e1", "Ana", T0, "v1");
    registrar("e2", "Bruno", T0, "v2");
    expect(listarUndosVivos("v1", T0).map((u) => u.nomeAluno)).toEqual(["Ana"]);
    expect(listarUndosVivos("v2", T0).map((u) => u.nomeAluno)).toEqual(["Bruno"]);
  });

  // O prazo é um instante absoluto justamente para isto: remontar o componente
  // (voltar de outra tela) não pode devolver tempo que já passou.
  it("o prazo não se renova ao ser lido de novo", () => {
    registrar("e1", "Ana", T0);
    const primeira = listarUndosVivos("v1", T0 + 5_000)[0].expiraEm;
    const segunda = listarUndosVivos("v1", T0 + 20_000)[0].expiraEm;
    expect(segunda).toBe(primeira);
  });

  it("registrar o mesmo eventId de novo não duplica a barra", () => {
    registrar("e1", "Ana", T0);
    registrar("e1", "Ana", T0 + 1_000);
    expect(listarUndosVivos("v1", T0 + 2_000)).toHaveLength(1);
  });

  it("avisa os assinantes ao registrar e ao descartar", () => {
    const ouvinte = jest.fn();
    const cancelar = require("../undoCheckin").assinarUndos(ouvinte);

    registrar("e1", "Ana", T0);
    expect(ouvinte).toHaveBeenCalledTimes(1);

    descartarUndo("e1");
    expect(ouvinte).toHaveBeenCalledTimes(2);

    // Descartar algo que não existe não deve acordar a tela à toa.
    descartarUndo("inexistente");
    expect(ouvinte).toHaveBeenCalledTimes(2);

    cancelar();
  });
});
