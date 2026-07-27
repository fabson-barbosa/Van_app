import type { Backend, ListAlunosParams } from './types';

const BASE = process.env.API_BASE_URL ?? 'http://localhost:8000';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    cache: 'no-store',
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => '');
    throw new Error(`API ${res.status} em ${path}: ${detail.slice(0, 200)}`);
  }
  return res.json() as Promise<T>;
}

/**
 * Cliente do FastAPI. Ainda não exercitado — o backend de auth não existe.
 * Quando existir: rode `npm run api:types` e troque os tipos abaixo pelos gerados.
 */
export const httpBackend: Backend = {
  async login(email, senha) {
    return request('/auth/login', { method: 'POST', body: JSON.stringify({ email, senha }) });
  },
  async listAlunos(params: ListAlunosParams) {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== '') as [string, string][],
    );
    return request(`/alunos?${qs}`);
  },
  async dashboardResumo() {
    return request('/dashboard/resumo');
  },
};
