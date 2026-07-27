'use client';
import * as React from 'react';
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
} from '@tanstack/react-table';
import { cn } from '@/lib/utils';
import { Spinner, ErrorState } from './feedback';
import { EmptyState } from './empty-state';
import { Button } from './button';
import { IconChevronLeft, IconChevronRight } from '@tabler/icons-react';

export interface DataTableProps<T> {
  columns: ColumnDef<T, unknown>[];
  data: T[] | undefined;
  loading?: boolean;
  error?: Error | null;
  onRetry?: () => void;
  empty?: React.ReactNode;
  total?: number;
  page?: number;
  pageSize?: number;
  onPageChange?: (page: number) => void;
  toolbar?: React.ReactNode;
  onRowClick?: (row: T) => void;
}

/**
 * Tabela padrão do painel.
 * Trata os quatro estados (carregando, erro, vazio, dados) num lugar só,
 * para que nenhuma tela precise reinventá-los.
 */
export function DataTable<T>({
  columns,
  data,
  loading,
  error,
  onRetry,
  empty,
  total = 0,
  page = 1,
  pageSize = 20,
  onPageChange,
  toolbar,
  onRowClick,
}: DataTableProps<T>) {
  const table = useReactTable({
    data: data ?? [],
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  const lastPage = Math.max(1, Math.ceil(total / pageSize));
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);

  return (
    <div className="rounded-[var(--radius-card)] border border-[var(--color-line)] bg-[var(--color-surface)] shadow-[var(--shadow-card)]">
      {toolbar && (
        <div className="flex flex-wrap items-center gap-2 border-b border-[var(--color-line)] bg-[var(--color-surface-2)] px-4.5 py-3">
          {toolbar}
        </div>
      )}

      {error ? (
        <ErrorState message={error.message} onRetry={onRetry} />
      ) : loading ? (
        <Spinner />
      ) : !data || data.length === 0 ? (
        (empty ?? <EmptyState title="Nada por aqui ainda" description="Nenhum registro encontrado com os filtros atuais." />)
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              {table.getHeaderGroups().map((hg) => (
                <tr key={hg.id}>
                  {hg.headers.map((h) => (
                    <th
                      key={h.id}
                      scope="col"
                      className="border-b border-[var(--color-line)] px-4.5 py-2.5 text-left text-[11px] font-bold tracking-wider whitespace-nowrap text-[var(--color-ink-3)] uppercase"
                    >
                      {h.isPlaceholder ? null : flexRender(h.column.columnDef.header, h.getContext())}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.map((row) => (
                <tr
                  key={row.id}
                  onClick={onRowClick ? () => onRowClick(row.original) : undefined}
                  className={cn(
                    'hover:bg-[var(--color-surface-2)]',
                    onRowClick && 'cursor-pointer',
                  )}
                >
                  {row.getVisibleCells().map((cell) => (
                    <td
                      key={cell.id}
                      className="border-b border-[var(--color-line)] px-4.5 py-3 align-middle text-[13.5px]"
                    >
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {onPageChange && !loading && !error && total > 0 && (
        <div className="flex items-center gap-3 border-t border-[var(--color-line)] px-4.5 py-3 text-xs text-[var(--color-ink-3)]">
          <span className="tabular">
            Mostrando {from}–{to} de {total}
          </span>
          <div className="ml-auto flex gap-1.5">
            <Button
              size="sm"
              onClick={() => onPageChange(page - 1)}
              disabled={page <= 1}
              aria-label="Página anterior"
            >
              <IconChevronLeft className="h-4 w-4" />
            </Button>
            <span className="tabular flex items-center px-2 font-semibold text-[var(--color-ink-2)]">
              {page} / {lastPage}
            </span>
            <Button
              size="sm"
              onClick={() => onPageChange(page + 1)}
              disabled={page >= lastPage}
              aria-label="Próxima página"
            >
              <IconChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
