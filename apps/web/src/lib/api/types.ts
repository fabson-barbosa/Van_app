import type { Aluno, Paginated, SessionUser } from '@/types';

export interface ListAlunosParams {
  q?: string;
  page?: number;
  pageSize?: number;
  turno?: string;
  status?: string;
  sort?: string;
}

/**
 * Contrato entre o painel e o backend.
 *
 * O mock e o cliente HTTP implementam esta mesma interface, então trocar
 * API_MODE=mock por API_MODE=http não exige mudar nenhuma tela.
 */
export interface Backend {
  login(email: string, senha: string): Promise<SessionUser | null>;
  listAlunos(params: ListAlunosParams): Promise<Paginated<Aluno>>;
  dashboardResumo(): Promise<{
    embarcados: number;
    totalAlunos: number;
    rotasAtrasadas: number;
    ocorrenciasAbertas: number;
    inadimplenciaCentavos: number;
  }>;
}
