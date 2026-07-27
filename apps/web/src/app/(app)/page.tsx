import { backend } from '@/lib/api';
import { requireSession } from '@/lib/auth/session';
import { PageHeader } from '@/components/ui/page-header';
import { Card } from '@/components/ui/card';
import { formatBRL } from '@/lib/utils';
import { can } from '@/lib/auth/permissions';
import { IconAlertTriangle, IconCash, IconClock, IconUserCheck } from '@tabler/icons-react';

function Kpi({
  label,
  value,
  foot,
  bar,
  icon,
}: {
  label: string;
  value: string;
  foot?: string;
  bar: string;
  icon: React.ReactNode;
}) {
  return (
    <Card className="relative overflow-hidden p-4.5">
      <span className="absolute inset-y-0 left-0 w-[3px]" style={{ background: bar }} />
      <div className="flex items-start gap-2">
        <div>
          <p className="text-[11.5px] font-semibold tracking-wide text-[var(--color-ink-3)] uppercase">
            {label}
          </p>
          <p className="tabular mt-2 font-[family-name:var(--font-display)] text-[30px] leading-none font-semibold">
            {value}
          </p>
          {foot && <p className="mt-2.5 text-xs text-[var(--color-ink-2)]">{foot}</p>}
        </div>
        <div className="ml-auto text-[var(--color-ink-3)]">{icon}</div>
      </div>
    </Card>
  );
}

export default async function DashboardPage() {
  const { user } = await requireSession();
  const resumo = await backend.dashboardResumo();
  const primeiroNome = user.name.split(' ')[0];

  return (
    <>
      <PageHeader
        title={`Bom dia, ${primeiroNome}`}
        description="Visão do turno atual. Cada número aqui leva a uma ação."
      />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Kpi
          label="Alunos embarcados"
          value={`${resumo.embarcados} / ${resumo.totalAlunos}`}
          foot={`${Math.round((resumo.embarcados / resumo.totalAlunos) * 100)}% do turno concluído`}
          bar="var(--color-ok)"
          icon={<IconUserCheck className="h-5 w-5" />}
        />
        <Kpi
          label="Rotas atrasadas"
          value={String(resumo.rotasAtrasadas)}
          foot="acima do limiar de 8 minutos"
          bar="var(--color-warn)"
          icon={<IconClock className="h-5 w-5" />}
        />
        <Kpi
          label="Ocorrências abertas"
          value={String(resumo.ocorrenciasAbertas)}
          foot="aguardando tratativa"
          bar="var(--color-danger)"
          icon={<IconAlertTriangle className="h-5 w-5" />}
        />
        {can(user.role, 'financeiro') && (
          <Kpi
            label="Inadimplência"
            value={formatBRL(resumo.inadimplenciaCentavos)}
            foot="7 mensalidades vencidas"
            bar="var(--color-accent)"
            icon={<IconCash className="h-5 w-5" />}
          />
        )}
      </div>

      <Card className="mt-4 p-4.5">
        <h2 className="text-[14.5px] font-semibold">Fase 0 concluída</h2>
        <p className="mt-1.5 max-w-2xl text-[13.5px] text-[var(--color-ink-2)]">
          Autenticação, RBAC, layout, design system e camada de dados estão de pé. As telas de
          negócio entram nas fases 1 a 3 — este dashboard é o esqueleto onde elas se encaixam.
        </p>
        <p className="mt-2.5 text-[13px] text-[var(--color-ink-3)]">
          Seu papel: <b className="text-[var(--color-ink-2)]">{user.role}</b>. Entre com outra conta
          de demonstração para ver o menu e os cartões mudarem conforme a permissão.
        </p>
      </Card>
    </>
  );
}
