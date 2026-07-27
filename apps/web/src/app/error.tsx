'use client';
import { useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { IconAlertTriangle } from '@tabler/icons-react';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Ponto de integração com Sentry/Datadog quando houver observabilidade.
    console.error(error);
  }, [error]);

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center px-6 text-center">
      <IconAlertTriangle className="h-8 w-8 text-[var(--color-danger)]" aria-hidden />
      <h1 className="mt-3 text-xl font-semibold">Algo quebrou aqui</h1>
      <p className="mt-1.5 max-w-md text-[13.5px] text-[var(--color-ink-2)]">
        O erro foi registrado. Você pode tentar de novo sem perder o que estava fazendo.
      </p>
      {error.digest && (
        <code className="mt-2 text-[11.5px] text-[var(--color-ink-3)]">ref: {error.digest}</code>
      )}
      <Button variant="primary" className="mt-5" onClick={reset}>
        Tentar de novo
      </Button>
    </div>
  );
}
