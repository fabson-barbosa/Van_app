'use client';
import * as React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { SessionProvider } from '@/components/auth/session-context';
import type { SessionUser } from '@/types';

/**
 * Política padrão de dados do painel.
 * Definida uma vez: nenhuma tela configura retry ou staleTime por conta própria.
 */
function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        gcTime: 5 * 60_000,
        refetchOnWindowFocus: false,
        retry: (failureCount, error) => {
          // 4xx é erro do cliente: repetir não resolve.
          const status = (error as { status?: number })?.status;
          if (status && status >= 400 && status < 500) return false;
          return failureCount < 2;
        },
      },
      mutations: { retry: 0 },
    },
  });
}

export function Providers({ user, children }: { user: SessionUser; children: React.ReactNode }) {
  const [client] = React.useState(makeQueryClient);
  return (
    <QueryClientProvider client={client}>
      <SessionProvider user={user}>{children}</SessionProvider>
    </QueryClientProvider>
  );
}
