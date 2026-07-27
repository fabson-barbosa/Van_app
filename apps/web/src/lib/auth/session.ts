import 'server-only';
import { cookies } from 'next/headers';
import { MAX_AGE_SECONDS, SESSION_COOKIE, unsealSession } from './jwt';
import type { Session } from '@/types';

export { SESSION_COOKIE, sealSession, unsealSession } from './jwt';

/** Sessão do request atual. `null` quando não autenticado. */
export async function getSession(): Promise<Session | null> {
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) return null;
  return unsealSession(token);
}

/**
 * Como acima, porém lança.
 * Use apenas em rotas já cobertas pelo middleware — se lançar, é bug de
 * configuração de rota, não fluxo de usuário não autenticado.
 */
export async function requireSession(): Promise<Session> {
  const session = await getSession();
  if (!session) throw new Error('Sessão ausente numa rota que deveria estar protegida.');
  return session;
}

export async function setSessionCookie(token: string) {
  (await cookies()).set(SESSION_COOKIE, token, {
    httpOnly: true, // JS da página nunca lê o token
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    path: '/',
    maxAge: MAX_AGE_SECONDS,
  });
}

export async function clearSessionCookie() {
  (await cookies()).delete(SESSION_COOKIE);
}
