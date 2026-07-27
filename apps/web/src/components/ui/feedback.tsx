import * as React from 'react';
import { IconAlertTriangle, IconLoader2 } from '@tabler/icons-react';
import { Button } from './button';

export function Spinner({ label = 'Carregando…' }: { label?: string }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-center justify-center gap-2 py-12 text-[13px] text-[var(--color-ink-3)]"
    >
      <IconLoader2 className="h-4 w-4 animate-spin" aria-hidden />
      {label}
    </div>
  );
}

export function Skeleton({ className = '' }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded-md bg-[var(--color-line)] ${className}`}
      aria-hidden="true"
    />
  );
}

export function ErrorState({ message, onRetry }: { message?: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-12 text-center">
      <IconAlertTriangle className="h-7 w-7 text-[var(--color-danger)]" aria-hidden />
      <p className="mt-2.5 font-[family-name:var(--font-display)] text-[15px] font-semibold">
        Não foi possível carregar
      </p>
      <p className="mt-1 max-w-sm text-[13px] text-[var(--color-ink-3)]">
        {message ?? 'Verifique sua conexão e tente novamente.'}
      </p>
      {onRetry && (
        <Button className="mt-4" onClick={onRetry}>
          Tentar de novo
        </Button>
      )}
    </div>
  );
}
