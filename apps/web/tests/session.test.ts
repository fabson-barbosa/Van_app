// @vitest-environment node

import { describe, expect, it } from 'vitest';
import { sealSession, unsealSession } from '@/lib/auth/jwt';
import type { SessionUser } from '@/types';

const user: SessionUser = {
  id: 'u1',
  name: 'Fábson Dekapoly',
  email: 'owner@aurora.com.br',
  role: 'owner',
  tenantId: 't1',
  tenantName: 'Transporte Aurora',
};

describe('sessão', () => {
  it('sela e abre preservando o usuário', async () => {
    const token = await sealSession(user);
    const session = await unsealSession(token);
    expect(session?.user.email).toBe(user.email);
    expect(session?.user.tenantId).toBe('t1');
  });

  it('rejeita token adulterado', async () => {
    const token = await sealSession(user);
    expect(await unsealSession(token.slice(0, -3) + 'aaa')).toBeNull();
  });

  it('rejeita lixo', async () => {
    expect(await unsealSession('não-é-um-jwt')).toBeNull();
  });
});
