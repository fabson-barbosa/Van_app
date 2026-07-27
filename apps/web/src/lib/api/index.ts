import 'server-only';
import type { Backend } from './types';
import { mockBackend } from '@/lib/mock/backend';
import { httpBackend } from './http-backend';

/**
 * Ponto único de troca entre mock e API real.
 * Nenhuma tela importa mock ou http diretamente — só `backend`.
 */
export const backend: Backend =
  process.env.API_MODE === 'http' ? httpBackend : mockBackend;

export type { Backend } from './types';
