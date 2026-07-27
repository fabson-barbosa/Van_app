'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  IconBus,
  IconCar,
  IconCash,
  IconChartBar,
  IconLayoutDashboard,
  IconMap2,
  IconMessage2,
  IconRoute,
  IconSettings,
  IconSteeringWheel,
  IconUsers,
} from '@tabler/icons-react';
import { NAV } from '@/lib/nav';
import { cn, initials } from '@/lib/utils';
import { useSessionUser } from '@/components/auth/session-context';
import { can, ROLE_LABEL } from '@/lib/auth/permissions';

const ICONS: Record<string, React.ElementType> = {
  dashboard: IconLayoutDashboard,
  map: IconMap2,
  route: IconRoute,
  users: IconUsers,
  wheel: IconSteeringWheel,
  car: IconCar,
  cash: IconCash,
  message: IconMessage2,
  chart: IconChartBar,
  settings: IconSettings,
};

export function Sidebar() {
  const pathname = usePathname();
  const user = useSessionUser();

  return (
    <aside className="sticky top-0 flex h-screen w-62 flex-col bg-[var(--color-graphite)] text-[#e8e4de]">
      <div className="flex items-center gap-2.5 border-b border-white/8 px-5 py-4">
        <div className="grid h-8 w-8 shrink-0 place-items-center rounded-[9px] bg-gradient-to-br from-[var(--color-accent)] to-[#8f6a22] text-[#1b1917]">
          <IconBus className="h-4.5 w-4.5" />
        </div>
        <div>
          <div className="font-[family-name:var(--font-display)] text-[15px] font-semibold">
            VaiVem
          </div>
          <div className="text-[10.5px] tracking-wider text-[#9a938a] uppercase">
            Painel do Gestor
          </div>
        </div>
      </div>

      <nav aria-label="Navegação principal" className="flex-1 overflow-y-auto p-3">
        {NAV.map((group) => {
          const visible = group.items.filter((i) => can(user.role, i.resource, i.action ?? 'read'));
          if (visible.length === 0) return null;
          return (
            <div key={group.label}>
              <p className="px-2 pt-3.5 pb-1.5 text-[10px] font-semibold tracking-widest text-[#7d766d] uppercase">
                {group.label}
              </p>
              {visible.map((item) => {
                const Icon = ICONS[item.icon] ?? IconLayoutDashboard;
                const active =
                  item.href === '/' ? pathname === '/' : pathname.startsWith(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    aria-current={active ? 'page' : undefined}
                    className={cn(
                      'mb-px flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13.5px] text-[#c9c3ba] transition-colors',
                      'hover:bg-white/5 hover:text-[#f0ece6]',
                      active && 'bg-[rgba(184,134,43,0.16)] font-semibold text-[#f3d9a0]',
                    )}
                  >
                    <Icon className="h-4.5 w-4.5 shrink-0" aria-hidden />
                    {item.label}
                  </Link>
                );
              })}
            </div>
          );
        })}
      </nav>

      <div className="flex items-center gap-2.5 border-t border-white/8 p-3">
        <div className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-[#4a4642] text-[11px] font-bold">
          {initials(user.name)}
        </div>
        <div className="min-w-0">
          <div className="truncate text-[12.5px] font-semibold">{user.name}</div>
          <div className="truncate text-[11px] text-[#8e8780]">
            {user.tenantName} · {ROLE_LABEL[user.role]}
          </div>
        </div>
      </div>
    </aside>
  );
}
