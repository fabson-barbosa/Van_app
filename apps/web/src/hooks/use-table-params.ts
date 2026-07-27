'use client';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import * as React from 'react';

/**
 * Filtros, busca e paginação vivem na URL — não em estado local.
 *
 * Ganhos: o link é compartilhável, o botão voltar funciona e um F5
 * não joga o gestor de volta à página 1 no meio de uma conferência.
 */
export function useTableParams(defaults: { pageSize?: number } = {}) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  const page = Number(params.get('page') ?? 1);
  const q = params.get('q') ?? '';
  const turno = params.get('turno') ?? '';
  const status = params.get('status') ?? '';
  const pageSize = Number(params.get('pageSize') ?? defaults.pageSize ?? 20);

  const setParam = React.useCallback(
    (patch: Record<string, string | number | undefined>) => {
      const next = new URLSearchParams(params.toString());
      for (const [key, value] of Object.entries(patch)) {
        if (value === undefined || value === '') next.delete(key);
        else next.set(key, String(value));
      }
      // Mudou filtro? Volta para a primeira página — senão o usuário vê "nenhum resultado".
      if (!('page' in patch)) next.delete('page');
      router.replace(`${pathname}?${next.toString()}`, { scroll: false });
    },
    [params, pathname, router],
  );

  return { page, pageSize, q, turno, status, setParam };
}
