import * as React from 'react';

/**
 * Estado vazio nunca é só "sem dados": diz o que aconteceu e oferece a próxima ação.
 * Tela sem EmptyState não passa na definição de pronto.
 */
export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-14 text-center">
      {icon && <div className="mb-3 text-[var(--color-ink-3)]">{icon}</div>}
      <p className="font-[family-name:var(--font-display)] text-[15px] font-semibold">{title}</p>
      {description && (
        <p className="mt-1 max-w-sm text-[13px] text-[var(--color-ink-3)]">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
