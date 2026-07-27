'use client';
import * as React from 'react';
import { useQuery, keepPreviousData } from '@tanstack/react-query';
import type { ColumnDef } from '@tanstack/react-table';
import { DataTable } from '@/components/ui/data-table';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';
import { Drawer } from '@/components/ui/drawer';
import { Can } from '@/components/auth/can';
import { useTableParams } from '@/hooks/use-table-params';
import { initials } from '@/lib/utils';
import type { Aluno, Paginated } from '@/types';
import { IconPlus, IconSearch, IconUsersGroup } from '@tabler/icons-react';

const STATUS_TONE = {
  em_dia: { tone: 'ok', label: 'Em dia' },
  vence_hoje: { tone: 'warn', label: 'Vence hoje' },
  vencida: { tone: 'danger', label: 'Vencida' },
} as const;

const columns: ColumnDef<Aluno, unknown>[] = [
  {
    header: 'Aluno',
    accessorKey: 'nome',
    cell: ({ row }) => (
      <div className="flex items-center gap-2.5">
        <span className="grid h-8 w-8 shrink-0 place-items-center rounded-[9px] border border-[var(--color-line)] bg-[var(--color-surface-2)] text-[11.5px] font-bold text-[var(--color-ink-2)]">
          {initials(row.original.nome)}
        </span>
        <span>
          <span className="block font-semibold">{row.original.nome}</span>
          <span className="block text-xs text-[var(--color-ink-3)]">
            {row.original.idade} anos · {row.original.serie}
          </span>
        </span>
      </div>
    ),
  },
  {
    header: 'Responsável',
    accessorKey: 'responsavelNome',
    cell: ({ row }) => (
      <span>
        <span className="block font-semibold">{row.original.responsavelNome}</span>
        <span className="tabular block text-xs text-[var(--color-ink-3)]">
          {row.original.responsavelTelefone}
        </span>
      </span>
    ),
  },
  { header: 'Escola', accessorKey: 'escola' },
  {
    header: 'Rota',
    accessorKey: 'rotaNome',
    cell: ({ row }) =>
      row.original.rotaNome ?? <Badge tone="warn">Sem rota</Badge>,
  },
  {
    header: 'Turno',
    accessorKey: 'turno',
    cell: ({ row }) => (row.original.turno === 'manha' ? 'Manhã' : 'Tarde'),
  },
  {
    header: 'Mensalidade',
    accessorKey: 'statusPagamento',
    cell: ({ row }) => {
      const s = STATUS_TONE[row.original.statusPagamento];
      return <Badge tone={s.tone}>{s.label}</Badge>;
    },
  },
];

export function AlunosTable() {
  const { page, pageSize, q, turno, status, setParam } = useTableParams();
  const [busca, setBusca] = React.useState(q);
  const [selecionado, setSelecionado] = React.useState<Aluno | null>(null);

  // Debounce da busca: sem isso, cada tecla vira uma requisição.
  React.useEffect(() => {
    const t = setTimeout(() => {
      if (busca !== q) setParam({ q: busca });
    }, 350);
    return () => clearTimeout(t);
  }, [busca, q, setParam]);

  const query = useQuery<Paginated<Aluno>>({
    queryKey: ['alunos', { page, pageSize, q, turno, status }],
    queryFn: async () => {
      const params = new URLSearchParams({ page: String(page), pageSize: String(pageSize) });
      if (q) params.set('q', q);
      if (turno) params.set('turno', turno);
      if (status) params.set('status', status);
      const res = await fetch(`/api/alunos?${params}`);
      if (!res.ok) throw new Error('Falha ao carregar alunos');
      return res.json();
    },
    placeholderData: keepPreviousData, // troca de página sem piscar a tabela
  });

  const filtros = [
    { key: 'turno', value: 'manha', label: 'Manhã' },
    { key: 'turno', value: 'tarde', label: 'Tarde' },
    { key: 'status', value: 'vencida', label: 'Inadimplentes' },
  ];
  const ativo = (key: string, value: string) => (key === 'turno' ? turno : status) === value;

  return (
    <>
      <DataTable
        columns={columns}
        data={query.data?.items}
        loading={query.isLoading}
        error={query.error as Error | null}
        onRetry={() => query.refetch()}
        total={query.data?.total ?? 0}
        page={page}
        pageSize={pageSize}
        onPageChange={(p) => setParam({ page: p })}
        onRowClick={setSelecionado}
        empty={
          <EmptyState
            icon={<IconUsersGroup className="h-8 w-8" />}
            title={q ? 'Nenhum aluno encontrado' : 'Nenhum aluno cadastrado'}
            description={
              q
                ? `Nada corresponde a "${q}". Tente outro termo ou limpe os filtros.`
                : 'Importe uma planilha para cadastrar a operação inteira de uma vez.'
            }
            action={
              q ? (
                <Button onClick={() => { setBusca(''); setParam({ q: '', turno: '', status: '' }); }}>
                  Limpar filtros
                </Button>
              ) : (
                <Can resource="alunos" action="create">
                  <Button variant="accent">
                    <IconPlus className="h-4 w-4" />
                    Importar planilha
                  </Button>
                </Can>
              )
            }
          />
        }
        toolbar={
          <>
            <div className="relative">
              <IconSearch
                className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-[var(--color-ink-3)]"
                aria-hidden
              />
              <Input
                value={busca}
                onChange={(e) => setBusca(e.target.value)}
                placeholder="Buscar aluno ou responsável…"
                aria-label="Buscar alunos"
                className="w-64 pl-9"
              />
            </div>
            {filtros.map((f) => (
              <Button
                key={f.key + f.value}
                size="sm"
                variant={ativo(f.key, f.value) ? 'accent' : 'default'}
                onClick={() => setParam({ [f.key]: ativo(f.key, f.value) ? '' : f.value })}
              >
                {f.label}
              </Button>
            ))}
            <span className="tabular ml-auto text-xs text-[var(--color-ink-3)]">
              {query.data?.total ?? 0} resultados
            </span>
          </>
        }
      />

      <Drawer
        open={!!selecionado}
        onClose={() => setSelecionado(null)}
        title={selecionado?.nome ?? ''}
        footer={
          <Can
            resource="alunos"
            action="update"
            fallback={
              <span className="self-center text-xs text-[var(--color-ink-3)]">
                Seu papel permite apenas leitura.
              </span>
            }
          >
            <Button variant="primary">Editar cadastro</Button>
          </Can>
        }
      >
        {selecionado && (
          <dl className="text-[13px]">
            {[
              ['Idade', `${selecionado.idade} anos`],
              ['Série', selecionado.serie],
              ['Escola', selecionado.escola],
              ['Rota', selecionado.rotaNome ?? 'Sem rota atribuída'],
              ['Turno', selecionado.turno === 'manha' ? 'Manhã' : 'Tarde'],
              ['Responsável', selecionado.responsavelNome],
              ['Telefone', selecionado.responsavelTelefone],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between border-b border-[var(--color-line)] py-2.5">
                <dt className="text-[var(--color-ink-3)]">{k}</dt>
                <dd className="font-semibold">{v}</dd>
              </div>
            ))}
          </dl>
        )}
      </Drawer>
    </>
  );
}
