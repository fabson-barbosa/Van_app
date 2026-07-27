'use client';
import * as React from 'react';
import { cn } from '@/lib/utils';
import { Button } from './button';
import { IconX } from '@tabler/icons-react';

/** Modal acessível sobre <dialog> nativo: foco, Esc e backdrop sem biblioteca. */
export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  className,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children?: React.ReactNode;
  footer?: React.ReactNode;
  className?: string;
}) {
  const ref = React.useRef<HTMLDialogElement>(null);

  React.useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (open && !el.open) el.showModal();
    if (!open && el.open) el.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      onClick={(e) => {
        if (e.target === ref.current) onClose();
      }}
      aria-labelledby="modal-title"
      className={cn(
        'm-auto w-[min(28rem,92vw)] rounded-[var(--radius-card)] border border-[var(--color-line)] bg-[var(--color-surface)] p-0 text-[var(--color-ink)] shadow-xl backdrop:bg-black/35',
        className,
      )}
    >
      <div className="flex items-start gap-3 border-b border-[var(--color-line)] px-4.5 py-3.5">
        <div>
          <h2 id="modal-title" className="text-[15px] font-semibold">
            {title}
          </h2>
          {description && (
            <p className="mt-0.5 text-[13px] text-[var(--color-ink-2)]">{description}</p>
          )}
        </div>
        <Button variant="ghost" size="icon" className="ml-auto" onClick={onClose} aria-label="Fechar">
          <IconX className="h-4 w-4" />
        </Button>
      </div>
      {children && <div className="px-4.5 py-4">{children}</div>}
      {footer && (
        <div className="flex justify-end gap-2 border-t border-[var(--color-line)] bg-[var(--color-surface-2)] px-4.5 py-3">
          {footer}
        </div>
      )}
    </dialog>
  );
}

export function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title,
  description,
  confirmLabel = 'Confirmar',
  destructive,
  loading,
}: {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  description?: string;
  confirmLabel?: string;
  destructive?: boolean;
  loading?: boolean;
}) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      description={description}
      footer={
        <>
          <Button onClick={onClose}>Cancelar</Button>
          <Button variant={destructive ? 'danger' : 'primary'} loading={loading} onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </>
      }
    />
  );
}
