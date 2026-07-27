'use client';
import * as React from 'react';
import { Button } from './button';
import { IconX } from '@tabler/icons-react';

/** Painel lateral para detalhe/edição sem perder o contexto da lista. */
export function Drawer({
  open,
  onClose,
  title,
  children,
  footer,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children?: React.ReactNode;
  footer?: React.ReactNode;
}) {
  React.useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} aria-hidden />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="relative flex h-full w-[min(30rem,94vw)] flex-col border-l border-[var(--color-line)] bg-[var(--color-surface)] shadow-2xl"
      >
        <header className="flex items-center gap-3 border-b border-[var(--color-line)] px-4.5 py-3.5">
          <h2 className="text-[15px] font-semibold">{title}</h2>
          <Button variant="ghost" size="icon" className="ml-auto" onClick={onClose} aria-label="Fechar">
            <IconX className="h-4 w-4" />
          </Button>
        </header>
        <div className="flex-1 overflow-y-auto px-4.5 py-4">{children}</div>
        {footer && (
          <footer className="flex justify-end gap-2 border-t border-[var(--color-line)] bg-[var(--color-surface-2)] px-4.5 py-3">
            {footer}
          </footer>
        )}
      </aside>
    </div>
  );
}
