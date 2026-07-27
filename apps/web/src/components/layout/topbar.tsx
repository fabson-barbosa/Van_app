'use client';
import { useRouter } from 'next/navigation';
import { IconBell, IconHelpCircle, IconLogout, IconSearch } from '@tabler/icons-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useSessionUser } from '@/components/auth/session-context';

export function Topbar({ crumb }: { crumb?: string }) {
  const router = useRouter();
  const user = useSessionUser();

  async function sair() {
    await fetch('/api/auth/logout', { method: 'POST' });
    router.replace('/login');
    router.refresh();
  }

  return (
    <header className="sticky top-0 z-20 flex h-15 items-center gap-4 border-b border-[var(--color-line)] bg-[var(--color-surface)] px-7">
      <p className="text-[12.5px] text-[var(--color-ink-3)]">
        {user.tenantName}
        {crumb && (
          <>
            {' / '}
            <span className="font-semibold text-[var(--color-ink)]">{crumb}</span>
          </>
        )}
      </p>

      <div className="relative ml-auto">
        <IconSearch
          className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-[var(--color-ink-3)]"
          aria-hidden
        />
        <Input
          className="w-65 bg-[var(--color-surface-2)] pl-9"
          placeholder="Buscar aluno, rota, motorista…"
          aria-label="Busca global"
        />
      </div>

      <Button variant="ghost" size="icon" aria-label="Notificações">
        <IconBell className="h-4.5 w-4.5" />
      </Button>
      <Button variant="ghost" size="icon" aria-label="Ajuda">
        <IconHelpCircle className="h-4.5 w-4.5" />
      </Button>
      <Button variant="ghost" size="icon" aria-label="Sair" onClick={sair}>
        <IconLogout className="h-4.5 w-4.5" />
      </Button>
    </header>
  );
}
