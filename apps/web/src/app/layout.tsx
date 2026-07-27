import type { Metadata } from 'next';
import { Plus_Jakarta_Sans, Sora } from 'next/font/google';
import './globals.css';

/**
 * next/font baixa e auto-hospeda as fontes no build:
 * sem requisição a terceiros em runtime, sem layout shift, sem rastreio externo.
 */
const sora = Sora({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  variable: '--font-sora',
  display: 'swap',
});

const jakarta = Plus_Jakarta_Sans({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  variable: '--font-jakarta',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'VaiVem — Painel do Gestor',
  description: 'Gestão de transporte escolar',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" className={`${sora.variable} ${jakarta.variable}`}>
      <body>{children}</body>
    </html>
  );
}
