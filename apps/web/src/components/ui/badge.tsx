import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const badgeVariants = cva(
  'inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-[11.5px] font-semibold whitespace-nowrap',
  {
    variants: {
      tone: {
        neutral:
          'bg-[var(--color-surface-2)] text-[var(--color-ink-2)] border border-[var(--color-line)]',
        ok: 'bg-[var(--color-ok-soft)] text-[var(--color-ok)]',
        warn: 'bg-[var(--color-warn-soft)] text-[var(--color-warn)]',
        danger: 'bg-[var(--color-danger-soft)] text-[var(--color-danger)]',
        info: 'bg-[var(--color-info-soft)] text-[var(--color-info)]',
      },
    },
    defaultVariants: { tone: 'neutral' },
  },
);

export function Badge({
  className,
  tone,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}
