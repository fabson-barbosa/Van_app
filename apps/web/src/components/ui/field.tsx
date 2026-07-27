import * as React from 'react';
import { cn } from '@/lib/utils';

interface FieldProps {
  label: string;
  htmlFor?: string;
  hint?: string;
  error?: string;
  required?: boolean;
  className?: string;
  children: React.ReactNode;
}

/** Rótulo, dica e erro num só lugar — evita cada tela inventar seu próprio formulário. */
export function Field({ label, htmlFor, hint, error, required, className, children }: FieldProps) {
  return (
    <div className={cn('mb-3.5', className)}>
      <label
        htmlFor={htmlFor}
        className="mb-1.5 block text-xs font-semibold text-[var(--color-ink-2)]"
      >
        {label}
        {required && <span className="ml-0.5 text-[var(--color-danger)]">*</span>}
      </label>
      {children}
      {error ? (
        <p role="alert" className="mt-1 text-[11.5px] font-medium text-[var(--color-danger)]">
          {error}
        </p>
      ) : hint ? (
        <p className="mt-1 text-[11.5px] text-[var(--color-ink-3)]">{hint}</p>
      ) : null}
    </div>
  );
}
