import * as React from 'react';

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="mb-5.5 flex items-start gap-4">
      <div>
        <h1 className="text-[23px] font-semibold">{title}</h1>
        {description && (
          <p className="mt-0.5 text-[13.5px] text-[var(--color-ink-2)]">{description}</p>
        )}
      </div>
      {actions && <div className="ml-auto flex shrink-0 gap-2">{actions}</div>}
    </div>
  );
}
