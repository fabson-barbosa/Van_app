import type { Backend, ListAlunosParams } from '@/lib/api/types';
import { MOCK_ALUNOS, MOCK_USERS } from './db';
import type { SessionUser } from '@/types';

/** Latência artificial: força as telas a tratarem estado de carregamento de verdade. */
const delay = (ms = 220) => new Promise((r) => setTimeout(r, ms));

export const mockBackend: Backend = {
  async login(email, senha) {
    await delay(400);
    const found = MOCK_USERS.find(
      (u) => u.email.toLowerCase() === email.toLowerCase().trim() && u.senha === senha,
    );
    if (!found) return null;
    const { senha: _omit, ...user } = found;
    return user as SessionUser;
  },

  async listAlunos({ q, page = 1, pageSize = 20, turno, status }: ListAlunosParams) {
    await delay();
    let items = MOCK_ALUNOS.filter((a) => a.ativo);
    if (q) {
      const needle = q.toLowerCase();
      items = items.filter(
        (a) =>
          a.nome.toLowerCase().includes(needle) ||
          a.responsavelNome.toLowerCase().includes(needle) ||
          a.escola.toLowerCase().includes(needle),
      );
    }
    if (turno) items = items.filter((a) => a.turno === turno);
    if (status) items = items.filter((a) => a.statusPagamento === status);

    const total = items.length;
    const start = (page - 1) * pageSize;
    return { items: items.slice(start, start + pageSize), total, page, pageSize };
  },

  async dashboardResumo() {
    await delay(160);
    return {
      embarcados: 118,
      totalAlunos: 134,
      rotasAtrasadas: 1,
      ocorrenciasAbertas: 2,
      inadimplenciaCentavos: 284000,
    };
  },
};
