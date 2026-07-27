import { Suspense } from 'react';
import { requireSession } from '@/lib/auth/session';
import { can } from '@/lib/auth/permissions';
import { forbidden } from '@/lib/forbidden';
import { AlunosTable } from './alunos-table';
import { PageHeader } from '@/components/ui/page-header';
import { Spinner } from '@/components/ui/feedback';

export default async function AlunosPage() {
  const { user } = await requireSession();
  if (!can(user.role, 'alunos', 'read')) return forbidden();

  return (
    <>
      <PageHeader
        title="Alunos"
        description="Referência de tela densa: busca, filtros e paginação sincronizados na URL."
      />
      <Suspense fallback={<Spinner />}>
        <AlunosTable />
      </Suspense>
    </>
  );
}
