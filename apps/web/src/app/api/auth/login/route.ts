import { NextResponse } from 'next/server';
import { backend } from '@/lib/api';
import { loginSchema } from '@/lib/auth/schemas';
import { sealSession, setSessionCookie } from '@/lib/auth/session';

/**
 * BFF de login.
 *
 * O token nunca chega ao browser: o handler autentica contra o backend,
 * sela a sessão e devolve apenas um cookie httpOnly. Assim um XSS na página
 * não consegue ler nem exfiltrar credencial.
 */
export async function POST(request: Request) {
  const body = await request.json().catch(() => null);
  const parsed = loginSchema.safeParse(body);

  if (!parsed.success) {
    return NextResponse.json(
      { error: 'Dados inválidos', issues: parsed.error.flatten().fieldErrors },
      { status: 422 },
    );
  }

  const user = await backend.login(parsed.data.email, parsed.data.senha);

  if (!user) {
    // Mensagem genérica de propósito: não revela se o e-mail existe.
    return NextResponse.json({ error: 'E-mail ou senha incorretos' }, { status: 401 });
  }

  await setSessionCookie(await sealSession(user));
  return NextResponse.json({ user });
}
