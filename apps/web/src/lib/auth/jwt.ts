import { SignJWT, jwtVerify } from 'jose';
import type { Session, SessionUser } from '@/types';

export const SESSION_COOKIE = 'vaivem_session';
export const MAX_AGE_SECONDS = 60 * 60 * 8; // 8h — jornada de trabalho, não sessão eterna

function secret() {
  const value = process.env.SESSION_SECRET;
  if (!value || value.length < 32) {
    throw new Error('SESSION_SECRET ausente ou com menos de 32 caracteres. Veja .env.example.');
  }
  return new TextEncoder().encode(value);
}

export async function sealSession(user: SessionUser) {
  return new SignJWT({ user })
    .setProtectedHeader({ alg: 'HS256' })
    .setIssuedAt()
    .setIssuer('vaivem-web')
    .setExpirationTime(`${MAX_AGE_SECONDS}s`)
    .sign(secret());
}

/** Verifica assinatura e validade. Roda no Edge (middleware) e no Node. */
export async function unsealSession(token: string): Promise<Session | null> {
  try {
    const { payload } = await jwtVerify(token, secret(), { issuer: 'vaivem-web' });
    if (!payload.user) return null;
    return { user: payload.user as SessionUser, exp: payload.exp ?? 0 };
  } catch {
    return null;
  }
}
