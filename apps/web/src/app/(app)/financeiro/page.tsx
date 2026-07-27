import { requireSession } from '@/lib/auth/session';
import { can } from '@/lib/auth/permissions';
import { forbidden } from '@/lib/forbidden';
import { PageHeader } from '@/components/ui/page-header';
import { Card, CardBody, CardHeader } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

/**
 * Placeholder deliberado: a Fase 0 entrega a rota protegida e a checagem
 * de permissão. O conteúdo real é a Fase 3.
 */
export default async function FinanceiroPage() {
  const { user } = await requireSession();
  if (!can(user.role, 'financeiro', 'read')) return forbidden();

  return (
    <>
      <PageHeader
        title="Financeiro"
        description="Rota protegida e permissão validada. Conteúdo entra na Fase 3."
      />
      <Card>
        <CardHeader title="Escopo previsto" right={<Badge tone="info">Fase 3</Badge>} />
        <CardBody className="text-[13.5px] text-[var(--color-ink-2)]">
          <ul className="list-inside list-disc space-y-1.5">
            <li>Contratos e geração de mensalidades em lote</li>
            <li>Régua de cobrança automática (D-3, D0, D+3, D+10)</li>
            <li>Conciliação de Pix e boleto</li>
            <li>Painel de inadimplência com renegociação</li>
            <li>Exportação para o contador</li>
          </ul>
          <p className="mt-4 text-[13px] text-[var(--color-ink-3)]">
            Entre como <b>auditor@aurora.com.br</b> para ver esta tela em modo somente leitura, ou
            como <b>financeiro@aurora.com.br</b> para ver o menu reduzido a este módulo.
          </p>
        </CardBody>
      </Card>
    </>
  );
}
