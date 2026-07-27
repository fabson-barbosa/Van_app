'use client';
import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';
import { IconLoader2 } from '@tabler/icons-react';

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 rounded-lg font-semibold transition-colors disabled:pointer-events-none disabled:opacity-50 whitespace-nowrap',
  {
    variants: {
      variant: {
        default:
          'border border-[var(--color-line-strong)] bg-[var(--color-surface)] text-[var(--color-ink)] hover:bg-[var(--color-surface-2)] hover:border-[var(--color-ink-3)]',
        primary:
          'border border-[var(--color-graphite)] bg-[var(--color-graphite)] text-[#f5f1eb] hover:bg-[var(--color-graphite-2)]',
        accent:
          'border border-[var(--color-accent)] bg-[var(--color-accent)] text-[#1f1b14] hover:bg-[var(--color-accent-strong)]',
        danger:
          'border border-[var(--color-danger)] bg-[var(--color-danger)] text-white hover:opacity-90',
        ghost: 'text-[var(--color-ink-2)] hover:bg-[var(--color-surface-2)] hover:text-[var(--color-ink)]',
      },
      size: {
        sm: 'h-8 px-2.5 text-xs',
        md: 'h-9 px-3.5 text-[13px]',
        icon: 'h-9 w-9 p-0',
      },
    },
    defaultVariants: { variant: 'default', size: 'md' },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  loading?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant, size, loading, children, disabled, ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      className={cn(buttonVariants({ variant, size }), className)}
      disabled={disabled || loading}
      {...props}
    >
      {loading && <IconLoader2 className="h-4 w-4 animate-spin" aria-hidden />}
      {children}
    </button>
  );
});
