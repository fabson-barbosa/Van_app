/**
 * RBAC do tenant.
 *
 * Permissão é declarada por par (recurso, ação) — nunca por tela.
 * A tela consulta a permissão; a permissão nunca conhece a tela.
 *
 * IMPORTANTE: isto é UX. O backend revalida toda escrita.
 * Esconder um botão não é controle de acesso.
 */

export const ROLES = ['owner', 'gestor', 'financeiro', 'auditor'] as const;
export type Role = (typeof ROLES)[number];

export const RESOURCES = [
  'dashboard',
  'operacao',
  'rotas',
  'alunos',
  'responsaveis',
  'motoristas',
  'veiculos',
  'financeiro',
  'comunicacao',
  'relatorios',
  'config',
  'usuarios',
  'billing',
  'auditoria',
] as const;
export type Resource = (typeof RESOURCES)[number];

export const ACTIONS = ['read', 'create', 'update', 'delete', 'export'] as const;
export type Action = (typeof ACTIONS)[number];

export type Permission = `${Resource}:${Action}`;

const ALL: Action[] = ['read', 'create', 'update', 'delete', 'export'];
const RW: Action[] = ['read', 'create', 'update', 'export'];
const RO: Action[] = ['read', 'export'];

function grant(map: Partial<Record<Resource, Action[]>>): Set<Permission> {
  const set = new Set<Permission>();
  for (const [resource, actions] of Object.entries(map)) {
    for (const action of actions as Action[]) set.add(`${resource as Resource}:${action}`);
  }
  return set;
}

const OPERATIONAL: Partial<Record<Resource, Action[]>> = {
  dashboard: RO,
  operacao: RW,
  rotas: ALL,
  alunos: ALL,
  responsaveis: ALL,
  motoristas: ALL,
  veiculos: ALL,
  comunicacao: RW,
  relatorios: RO,
};

export const ROLE_PERMISSIONS: Record<Role, Set<Permission>> = {
  // Owner: tudo, inclusive assinatura do SaaS e exclusão da conta.
  owner: grant(
    Object.fromEntries(RESOURCES.map((r) => [r, ALL])) as Record<Resource, Action[]>,
  ),

  // Gestor: operação completa + financeiro, sem billing do SaaS nem gestão de usuários.
  gestor: grant({
    ...OPERATIONAL,
    financeiro: RW,
    config: ['read', 'update'],
    auditoria: ['read'],
  }),

  // Financeiro: só dinheiro. Sem acesso a rota, localização ou dado de criança.
  financeiro: grant({
    dashboard: ['read'],
    financeiro: RW,
    relatorios: RO,
  }),

  // Auditor (contador externo, sócio): leitura em tudo, escrita em nada.
  auditor: grant(
    Object.fromEntries(RESOURCES.map((r) => [r, RO])) as Record<Resource, Action[]>,
  ),
};

export function can(role: Role | undefined, resource: Resource, action: Action = 'read') {
  if (!role) return false;
  return ROLE_PERMISSIONS[role].has(`${resource}:${action}`);
}

export const ROLE_LABEL: Record<Role, string> = {
  owner: 'Proprietário',
  gestor: 'Gestor',
  financeiro: 'Financeiro',
  auditor: 'Auditor',
};
