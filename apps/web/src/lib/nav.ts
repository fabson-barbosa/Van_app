import type { Action, Resource } from '@/lib/auth/permissions';

export interface NavItem {
  href: string;
  label: string;
  icon: string; // nome do ícone Tabler, resolvido no componente
  resource: Resource;
  action?: Action;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

/**
 * Navegação declarada como dado, não como JSX.
 * Cada item traz o par (recurso, ação) que o habilita — a sidebar
 * filtra sozinha conforme o papel, sem `if` espalhado pelo componente.
 */
export const NAV: NavGroup[] = [
  {
    label: 'Operação',
    items: [
      { href: '/', label: 'Dashboard', icon: 'dashboard', resource: 'dashboard' },
      { href: '/operacao', label: 'Ao vivo', icon: 'map', resource: 'operacao' },
      { href: '/rotas', label: 'Rotas', icon: 'route', resource: 'rotas' },
    ],
  },
  {
    label: 'Cadastros',
    items: [
      { href: '/alunos', label: 'Alunos', icon: 'users', resource: 'alunos' },
      { href: '/motoristas', label: 'Motoristas', icon: 'wheel', resource: 'motoristas' },
      { href: '/veiculos', label: 'Veículos', icon: 'car', resource: 'veiculos' },
    ],
  },
  {
    label: 'Gestão',
    items: [
      { href: '/financeiro', label: 'Financeiro', icon: 'cash', resource: 'financeiro' },
      { href: '/comunicacao', label: 'Comunicação', icon: 'message', resource: 'comunicacao' },
      { href: '/relatorios', label: 'Relatórios', icon: 'chart', resource: 'relatorios' },
      { href: '/config', label: 'Configurações', icon: 'settings', resource: 'config' },
    ],
  },
];
