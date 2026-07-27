'use client';
import { useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { loginSchema, type LoginInput } from '@/lib/auth/schemas';
import { Field } from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { IconAlertCircle } from '@tabler/icons-react';

export function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get('next') || '/';
  const [erroServidor, setErroServidor] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginInput>({ resolver: zodResolver(loginSchema) });

  async function onSubmit(values: LoginInput) {
    setErroServidor(null);
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(values),
    });

    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      setErroServidor(body.error ?? 'Não foi possível entrar. Tente novamente.');
      return;
    }

    router.replace(next);
    router.refresh();
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate>
      {erroServidor && (
        <div
          role="alert"
          className="mb-4 flex items-start gap-2 rounded-lg border border-[var(--color-danger)]/25 bg-[var(--color-danger-soft)] px-3 py-2.5 text-[13px] text-[var(--color-danger)]"
        >
          <IconAlertCircle className="mt-px h-4 w-4 shrink-0" aria-hidden />
          {erroServidor}
        </div>
      )}

      <Field label="E-mail" htmlFor="email" error={errors.email?.message} required>
        <Input
          id="email"
          type="email"
          autoComplete="email"
          autoFocus
          aria-invalid={!!errors.email}
          placeholder="voce@suatransportadora.com.br"
          {...register('email')}
        />
      </Field>

      <Field label="Senha" htmlFor="senha" error={errors.senha?.message} required>
        <Input
          id="senha"
          type="password"
          autoComplete="current-password"
          aria-invalid={!!errors.senha}
          {...register('senha')}
        />
      </Field>

      <Button type="submit" variant="primary" className="mt-1 w-full" loading={isSubmitting}>
        Entrar
      </Button>

      <div className="mt-6 rounded-lg border border-[var(--color-accent-line)] bg-[var(--color-accent-soft)] px-3.5 py-3 text-[12.5px] text-[#6b4c13]">
        <p className="mb-1.5 font-bold">Contas de demonstração (senha: vaivem123)</p>
        <ul className="space-y-0.5">
          <li>owner@aurora.com.br — acesso total</li>
          <li>gestor@aurora.com.br — operação e financeiro</li>
          <li>financeiro@aurora.com.br — só financeiro</li>
          <li>auditor@aurora.com.br — somente leitura</li>
        </ul>
      </div>
    </form>
  );
}
