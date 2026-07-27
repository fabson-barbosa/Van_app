import { redirect } from 'next/navigation';
import { getSession } from '@/lib/auth/session';
import { Providers } from '@/components/providers';
import { Sidebar } from '@/components/layout/sidebar';
import { Topbar } from '@/components/layout/topbar';

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const session = await getSession();
  // Cinto e suspensório: o middleware já barra, isto cobre chamada direta ao RSC.
  if (!session) redirect('/login');

  return (
    <Providers user={session.user}>
      <div className="grid min-h-screen grid-cols-[15.5rem_1fr]">
        <Sidebar />
        <div className="flex min-w-0 flex-col">
          <Topbar />
          <main className="w-full max-w-350 px-7 pt-6.5 pb-12">{children}</main>
        </div>
      </div>
    </Providers>
  );
}
