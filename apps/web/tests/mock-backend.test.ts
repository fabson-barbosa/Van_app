// @vitest-environment node

import { describe, expect, it } from 'vitest';
import { mockBackend } from '@/lib/mock/backend';

describe('backend mock', () => {
  it('autentica com credencial correta', async () => {
    const user = await mockBackend.login('owner@aurora.com.br', 'vaivem123');
    expect(user?.role).toBe('owner');
  });

  it('recusa senha errada sem vazar existência do e-mail', async () => {
    expect(await mockBackend.login('owner@aurora.com.br', 'errada')).toBeNull();
    expect(await mockBackend.login('ninguem@aurora.com.br', 'vaivem123')).toBeNull();
  });

  it('pagina alunos', async () => {
    const p1 = await mockBackend.listAlunos({ page: 1, pageSize: 10 });
    const p2 = await mockBackend.listAlunos({ page: 2, pageSize: 10 });
    expect(p1.items).toHaveLength(10);
    expect(p1.items[0].id).not.toBe(p2.items[0].id);
    expect(p1.total).toBeGreaterThan(100);
  });

  it('filtra por busca e por turno', async () => {
    const busca = await mockBackend.listAlunos({ q: 'Laura' });
    expect(busca.items.every((a) => a.nome.includes('Laura'))).toBe(true);

    const manha = await mockBackend.listAlunos({ turno: 'manha' });
    expect(manha.items.every((a) => a.turno === 'manha')).toBe(true);
  });
});
