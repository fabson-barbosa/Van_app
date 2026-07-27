import { NextResponse, type NextRequest } from 'next/server';
import { SESSION_COOKIE, unsealSession } from '@/lib/auth/jwt';

const PUBLIC_PATHS = ['/login', '/recuperar-senha'];

/**
 * Guarda de rota na borda.
 *
 * Verificar aqui — e não dentro da página — evita o "flash" de tela protegida
 * antes do redirecionamento, e mantém uma só regra de acesso para todo o painel.
 */
export async function middleware(req: NextRequest) {
  const { pathname, search } = req.nextUrl;
  const isPublic = PUBLIC_PATHS.some((p) => pathname.startsWith(p));

  const token = req.cookies.get(SESSION_COOKIE)?.value;
  const session = token ? await unsealSession(token) : null;

  if (!session && !isPublic) {
    const url = req.nextUrl.clone();
    url.pathname = '/login';
    url.search = `?next=${encodeURIComponent(pathname + search)}`;
    return NextResponse.redirect(url);
  }

  if (session && isPublic) {
    const url = req.nextUrl.clone();
    url.pathname = '/';
    url.search = '';
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  // Tudo exceto estáticos, imagens do Next e as rotas de auth da API.
  matcher: ['/((?!api/auth|_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|webp)$).*)'],
};
