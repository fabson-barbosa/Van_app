import { requireSession } from '@/lib/auth/session';
import { can, ROLE_LABEL, ROLE_PERMISSIONS, ROLES } from '@/lib/auth/permissions';
import { forbidden } from '@/lib/forbidden';
import { PageHeader } from '@/components/ui/page-header';
import { Card, CardBody, CardHeader } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

/** Matriz de permissões visível ao usuário — documentação viva do RBAC. */
export default async function ConfigPage() {
  const { user } = await requireSession();
  if (!can(user.role, 'config', 'read')) return forbidden();

  return (
    <>
      <PageHeader
        title="Configurações"
        description="Papéis e permissões em vigor nesta conta."
      />
      <Card>
        <CardHeader
          title="Matriz de permissões"
          sub="gerada a partir do código, nunca de uma tabela escrita à mão"
        />
        <CardBody>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {ROLES.map((role) => (
              <div
                key={role}
                className="rounded-lg border border-[var(--color-line)] bg-[var(--color-surface-2)] p-3.5"
              >
                <div className="mb-2 flex items-center gap-2">
                  <p className="font-[family-name:var(--font-display)] text-[13.5px] font-semibold">
                    {ROLE_LABEL[role]}
                  </p>
                  {role === user.role && <Badge tone="ok">você</Badge>}
                </div>
                <p className="tabular text-xs text-[var(--color-ink-3)]">
                  {ROLE_PERMISSIONS[role].size} permissões
                </p>
              </div>
            ))}
          </div>
        </CardBody>
      </Card>
    </>
  );
}
