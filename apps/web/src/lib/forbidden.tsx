import Link from 'next/link';
import { IconLock } from '@tabler/icons-react';

/** Tela de 403. Explica e oferece saída — não é um beco sem mensagem. */
export function forbidden(
  message = 'Seu papel nesta conta não dá acesso a esta área. Peça ao proprietário para ajustar suas permissões.',
) {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <IconLock className="h-8 w-8 text-[var(--color-ink-3)]" aria-hidden />
      <h1 className="mt-3 text-xl font-semibold">Acesso não permitido</h1>
      <p className="mt-1.5 max-w-md text-[13.5px] text-[var(--color-ink-2)]">{message}</p>
      <Link
        href="/"
        className="mt-5 rounded-lg border border-[var(--color-line-strong)] bg-white px-3.5 py-2 text-[13px] font-semibold hover:bg-[var(--color-surface-2)]"
      >
        Voltar ao dashboard
      </Link>
    </div>
  );
}
