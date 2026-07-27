import * as React from 'react';
import { cn } from '@/lib/utils';

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        'rounded-[var(--radius-card)] border border-[var(--color-line)] bg-[var(--color-surface)] shadow-[var(--shadow-card)]',
        className,
      )}
      {...props}
    />
  );
}

export function CardHeader({
  title,
  sub,
  right,
  className,
}: {
  title: string;
  sub?: string;
  right?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        'flex items-center gap-2.5 border-b border-[var(--color-line)] px-4.5 py-3.5',
        className,
      )}
    >
      <h3 className="text-[14.5px] font-semibold">{title}</h3>
      {sub && <span className="text-xs text-[var(--color-ink-3)]">{sub}</span>}
      {right && <div className="ml-auto flex items-center gap-1.5">{right}</div>}
    </div>
  );
}

export function CardBody({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('p-4.5', className)} {...props} />;
}
