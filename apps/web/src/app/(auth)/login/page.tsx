import { Suspense } from 'react';
import { LoginForm } from './login-form';
import { IconBus } from '@tabler/icons-react';

export default function LoginPage() {
  return (
    <main className="grid min-h-screen lg:grid-cols-2">
      <div className="flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex items-center gap-2.5">
            <div className="grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br from-[var(--color-accent)] to-[#8f6a22] text-[#1b1917]">
              <IconBus className="h-5 w-5" />
            </div>
            <div>
              <p className="font-[family-name:var(--font-display)] text-lg font-semibold">VaiVem</p>
              <p className="text-[11px] tracking-wider text-[var(--color-ink-3)] uppercase">
                Painel do Gestor
              </p>
            </div>
          </div>

          <h1 className="text-2xl font-semibold">Entrar</h1>
          <p className="mt-1 mb-6 text-[13.5px] text-[var(--color-ink-2)]">
            Acesse com a conta da sua transportadora.
          </p>

          <Suspense>
            <LoginForm />
          </Suspense>
        </div>
      </div>

      <aside className="hidden flex-col justify-end bg-[var(--color-graphite)] p-12 text-[#c9c3ba] lg:flex">
        <blockquote className="max-w-md">
          <p className="font-[family-name:var(--font-display)] text-xl leading-snug text-[#f0ece6]">
            Toda criança embarcada, conferida e entregue — com registro de quem, quando e onde.
          </p>
          <footer className="mt-4 text-[13px] text-[#8e8780]">
            Varredura de fim de rota obrigatória. ETA dinâmico no lugar de raio fixo.
          </footer>
        </blockquote>
      </aside>
    </main>
  );
}
