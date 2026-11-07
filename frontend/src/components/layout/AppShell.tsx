import { NavLink, Outlet } from 'react-router';
import { useQuery } from '@tanstack/react-query';

import { api, type Capabilities } from '@/api/client';
import { Icon, type IconName } from '@/components/ui/Icon';
import { Wordmark } from '@/components/ui/Wordmark';
import { useAuth } from '@/lib/auth';

const NAV: { to: string; label: string; icon: IconName; capability?: string }[] = [
  { to: '/', label: 'Dashboard', icon: 'dashboard' },
  { to: '/documents', label: 'Library', icon: 'library' },
  { to: '/inspect', label: 'Inspection', icon: 'inspect', capability: 'inspect' },
  { to: '/standards', label: 'Standards', icon: 'standard', capability: 'standards' },
  { to: '/quality', label: 'Quality', icon: 'quality', capability: 'visual' },
];

export function useCapabilities() {
  return useQuery({ queryKey: ['capabilities'], queryFn: () => api<Capabilities>('/capabilities'), staleTime: 300_000 });
}

export function AppShell() {
  const { user, logout } = useAuth();
  const caps = useCapabilities();
  const phaseOf = (key?: string) => caps.data?.capabilities.find((c) => c.key === key);

  return (
    <div className="ruled grid min-h-dvh grid-cols-[minmax(0,1fr)] md:grid-cols-[15.5rem_minmax(0,1fr)]">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded focus:bg-accent focus:px-3 focus:py-2 focus:text-ink-950">
        Skip to content
      </a>
      <aside className="sticky top-0 z-20 flex min-w-0 flex-col border-b border-ink-700 bg-ink-950/85 backdrop-blur md:h-dvh md:border-r md:border-b-0">
        <div className="flex h-16 items-center justify-between px-5">
          <Wordmark />
          <div className="flex items-center gap-1 md:hidden">
            <NavLink to="/settings" aria-label="Settings" className="grid size-9 place-items-center rounded-lg text-paper-dim hover:bg-ink-800 hover:text-paper">
              <Icon name="settings" />
            </NavLink>
            <button onClick={() => void logout()} aria-label="Sign out" className="grid size-9 place-items-center rounded-lg text-paper-dim hover:bg-ink-800 hover:text-paper">
              <Icon name="logout" />
            </button>
          </div>
        </div>
        <nav aria-label="Primary" className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-1 md:flex-col md:pb-0">
          {NAV.map((item) => {
            const cap = phaseOf(item.capability);
            const locked = item.capability && cap && !cap.available;
            if (locked) {
              return (
                <span
                  key={item.to}
                  aria-disabled="true"
                  title={`Arrives in Phase ${cap.phase}`}
                  className="flex shrink-0 cursor-not-allowed items-center gap-3 rounded-lg px-3 py-2 text-sm text-paper-faint/70"
                >
                  <Icon name={item.icon} />
                  {item.label}
                  <span className="ml-auto hidden rounded border border-ink-700 px-1.5 font-mono text-[10px] md:inline">P{cap.phase}</span>
                </span>
              );
            }
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  `flex shrink-0 items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors ${
                    isActive
                      ? 'bg-accent-soft text-paper shadow-[inset_2px_0_0_var(--color-accent)]'
                      : 'text-paper-dim hover:bg-ink-800 hover:text-paper'
                  }`
                }
              >
                <Icon name={item.icon} />
                {item.label}
              </NavLink>
            );
          })}
        </nav>
        <div className="hidden border-t border-ink-700 p-3 md:block">
          <NavLink
            to="/settings"
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-2 text-sm ${isActive ? 'bg-accent-soft text-paper' : 'text-paper-dim hover:bg-ink-800 hover:text-paper'}`
            }
          >
            <span className="grid size-7 place-items-center rounded-full bg-ink-700 font-serif text-sm text-gold">
              {(user?.display_name || user?.email || '?').charAt(0).toUpperCase()}
            </span>
            <span className="min-w-0 flex-1 truncate">{user?.display_name || user?.email}</span>
            <Icon name="settings" className="size-4 text-paper-faint" />
          </NavLink>
          <button
            onClick={() => void logout()}
            className="mt-1 flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-paper-faint hover:bg-ink-800 hover:text-paper"
          >
            <Icon name="logout" />
            Sign out
          </button>
        </div>
      </aside>
      <main id="main" className="min-w-0 px-5 py-8 md:px-10 md:py-10">
        <Outlet />
      </main>
    </div>
  );
}
