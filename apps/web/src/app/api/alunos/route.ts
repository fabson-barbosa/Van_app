import { NextResponse } from 'next/server';
import { backend } from '@/lib/api';
import { getSession } from '@/lib/auth/session';
import { can } from '@/lib/auth/permissions';

export async function GET(request: Request) {
  const session = await getSession();
  if (!session) return NextResponse.json({ error: 'Não autenticado' }, { status: 401 });

  // Revalidação no servidor: esconder o menu no front não basta.
  if (!can(session.user.role, 'alunos', 'read')) {
    return NextResponse.json({ error: 'Sem permissão' }, { status: 403 });
  }

  const url = new URL(request.url);
  const data = await backend.listAlunos({
    q: url.searchParams.get('q') ?? undefined,
    page: Number(url.searchParams.get('page') ?? 1),
    pageSize: Number(url.searchParams.get('pageSize') ?? 20),
    turno: url.searchParams.get('turno') ?? undefined,
    status: url.searchParams.get('status') ?? undefined,
  });

  return NextResponse.json(data);
}
