'use client';
import * as React from 'react';
import { cn } from '@/lib/utils';

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, ...props }, ref) {
    return (
      <input
        ref={ref}
        className={cn(
          'h-9 w-full rounded-lg border border-[var(--color-line-strong)] bg-white px-3 text-[13px] text-[var(--color-ink)] placeholder:text-[var(--color-ink-3)]',
          'focus:outline-2 focus:outline-offset-[-1px] focus:outline-[var(--color-accent-line)]',
          'aria-[invalid=true]:border-[var(--color-danger)]',
          className,
        )}
        {...props}
      />
    );
  },
);

export const Select = React.forwardRef<
  HTMLSelectElement,
  React.SelectHTMLAttributes<HTMLSelectElement>
>(function Select({ className, ...props }, ref) {
  return (
    <select
      ref={ref}
      className={cn(
        'h-9 w-full rounded-lg border border-[var(--color-line-strong)] bg-white px-2.5 text-[13px] text-[var(--color-ink)]',
        className,
      )}
      {...props}
    />
  );
});
