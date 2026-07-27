import { agoraISO } from "../relogio";

describe("agoraISO", () => {
  it("devolve um instante em formato ISO 8601 válido, comparável a Date", () => {
    const antes = Date.now();
    const carimbo = agoraISO();
    const depois = Date.now();

    expect(carimbo).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/);

    const instante = new Date(carimbo).getTime();
    expect(instante).toBeGreaterThanOrEqual(antes);
    expect(instante).toBeLessThanOrEqual(depois);
  });
});
