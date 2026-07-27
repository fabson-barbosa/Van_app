import Link from 'next/link';

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-6 text-center">
      <p className="font-[family-name:var(--font-display)] text-5xl font-semibold text-[var(--color-line-strong)]">
        404
      </p>
      <h1 className="mt-3 text-xl font-semibold">Página não encontrada</h1>
      <p className="mt-1.5 text-[13.5px] text-[var(--color-ink-2)]">
        O endereço não existe ou foi movido.
      </p>
      <Link
        href="/"
        className="mt-5 rounded-lg border border-[var(--color-line-strong)] bg-white px-3.5 py-2 text-[13px] font-semibold hover:bg-[var(--color-surface-2)]"
      >
        Voltar ao início
      </Link>
    </div>
  );
}
