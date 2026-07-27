// @vitest-environment node

import { describe, expect, it } from 'vitest';
import { can, ROLES, ROLE_PERMISSIONS } from '@/lib/auth/permissions';

describe('RBAC', () => {
  it('owner faz tudo, inclusive billing', () => {
    expect(can('owner', 'billing', 'update')).toBe(true);
    expect(can('owner', 'alunos', 'delete')).toBe(true);
  });

  it('gestor opera, mas não mexe em billing nem em usuários', () => {
    expect(can('gestor', 'alunos', 'create')).toBe(true);
    expect(can('gestor', 'financeiro', 'update')).toBe(true);
    expect(can('gestor', 'billing', 'read')).toBe(false);
    expect(can('gestor', 'usuarios', 'create')).toBe(false);
  });

  it('financeiro não enxerga dado de criança nem de rota', () => {
    expect(can('financeiro', 'financeiro', 'update')).toBe(true);
    expect(can('financeiro', 'alunos', 'read')).toBe(false);
    expect(can('financeiro', 'operacao', 'read')).toBe(false);
    expect(can('financeiro', 'rotas', 'read')).toBe(false);
  });

  it('auditor lê tudo e não escreve nada', () => {
    expect(can('auditor', 'financeiro', 'read')).toBe(true);
    expect(can('auditor', 'alunos', 'read')).toBe(true);
    for (const action of ['create', 'update', 'delete'] as const) {
      expect(can('auditor', 'alunos', action)).toBe(false);
    }
  });

  it('sem papel, sem acesso', () => {
    expect(can(undefined, 'dashboard', 'read')).toBe(false);
  });

  it('todo papel tem ao menos uma permissão', () => {
    for (const role of ROLES) expect(ROLE_PERMISSIONS[role].size).toBeGreaterThan(0);
  });
});
