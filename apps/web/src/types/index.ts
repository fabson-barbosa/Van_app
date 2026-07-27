import type { Role } from '@/lib/auth/permissions';

export interface SessionUser {
  id: string;
  name: string;
  email: string;
  role: Role;
  tenantId: string;
  tenantName: string;
}

export interface Session {
  user: SessionUser;
  exp: number;
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
}

export interface Aluno {
  id: string;
  nome: string;
  idade: number;
  serie: string;
  escola: string;
  rotaId: string | null;
  rotaNome: string | null;
  turno: 'manha' | 'tarde';
  responsavelNome: string;
  responsavelTelefone: string;
  statusPagamento: 'em_dia' | 'vence_hoje' | 'vencida';
  ativo: boolean;
}
