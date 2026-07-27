import { requireSession } from '@/lib/auth/session';
import { can, type Resource } from '@/lib/auth/permissions';
import { forbidden } from '@/lib/forbidden';
import { PageHeader } from '@/components/ui/page-header';
import { Card, CardBody, CardHeader } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

/**
 * Rota real, protegida e navegável — com o escopo previsto à vista.
 * Melhor do que um 404: o gestor entende que o módulo existe e quando chega.
 */
export async function EmScopoPage({
  resource,
  title,
  fase,
  itens,
}: {
  resource: Resource;
  title: string;
  fase: string;
  itens: string[];
}) {
  const { user } = await requireSession();
  if (!can(user.role, resource, 'read')) return forbidden();

  return (
    <>
      <PageHeader title={title} description="Rota protegida pelo middleware e pela permissão do papel." />
      <Card>
        <CardHeader title="Escopo previsto" right={<Badge tone="info">{fase}</Badge>} />
        <CardBody>
          <ul className="list-inside list-disc space-y-1.5 text-[13.5px] text-[var(--color-ink-2)]">
            {itens.map((i) => (
              <li key={i}>{i}</li>
            ))}
          </ul>
        </CardBody>
      </Card>
    </>
  );
}
