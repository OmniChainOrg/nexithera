'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Activity,
  Beaker,
  GitBranch,
  Home,
  LayoutDashboard,
  Microscope,
  Network,
  Settings,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import { cn } from '@/lib/utils/cn';
import { useUIStore } from '@/lib/stores/ui-store';
import { useProgramStore } from '@/lib/stores/program-store';

interface NavItem {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  /** Whether this item requires a selected program. */
  programScoped?: boolean;
}

const PRIMARY_NAV: NavItem[] = [
  { href: '/', label: 'Overview', icon: Home },
  { href: '/evidence-graph', label: 'Evidence Graph', icon: Network },
  { href: '/agent-runs', label: 'Agent Runs', icon: Activity },
  { href: '/target-discovery', label: 'Targets', icon: Sparkles },
  { href: '/gaps', label: 'Gaps', icon: Network },
  { href: '/experiments', label: 'Experiments', icon: Beaker },
  { href: '/pipeline/bulk', label: 'Bulk Review', icon: ShieldCheck },
  { href: '/settings', label: 'Settings', icon: Settings },
];

const PROGRAM_NAV: NavItem[] = [
  { href: '/overview', label: 'Overview', icon: LayoutDashboard, programScoped: true },
  { href: '/evidence', label: 'Evidence', icon: Network, programScoped: true },
  { href: '/hypotheses', label: 'Hypotheses', icon: Sparkles, programScoped: true },
  { href: '/candidates', label: 'Candidates', icon: Beaker, programScoped: true },
  { href: '/agents', label: 'Agents', icon: Microscope, programScoped: true },
  { href: '/guardian', label: 'Guardian', icon: ShieldCheck, programScoped: true },
  { href: '/simulations', label: 'Simulations', icon: GitBranch, programScoped: true },
];

export function Sidebar() {
  const pathname = usePathname();
  const collapsed = useUIStore((s) => s.sidebarCollapsed);
  const currentProgramId = useProgramStore((s) => s.currentProgramId);

  return (
    <aside
      className={cn(
        'sticky top-0 hidden h-screen shrink-0 border-r bg-card transition-[width] md:flex md:flex-col',
        collapsed ? 'w-16' : 'w-60',
      )}
      aria-label="Primary"
    >
      <div className="flex h-14 items-center gap-2 border-b px-4">
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <Sparkles className="h-4 w-4" />
        </div>
        {!collapsed && <span className="text-sm font-semibold tracking-tight">Genovate</span>}
      </div>

      <nav className="flex flex-1 flex-col gap-1 overflow-y-auto p-2 text-sm">
        {PRIMARY_NAV.map((item) => (
          <NavLink key={item.href} item={item} pathname={pathname} collapsed={collapsed} />
        ))}

        {currentProgramId && (
          <>
            <div
              className={cn(
                'mt-4 px-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground',
                collapsed && 'sr-only',
              )}
            >
              Program
            </div>
            {PROGRAM_NAV.map((item) => {
              const programHref = `/programs/${currentProgramId}${item.href}`;
              return (
                <NavLink
                  key={item.href}
                  item={{ ...item, href: programHref }}
                  pathname={pathname}
                  collapsed={collapsed}
                />
              );
            })}
          </>
        )}
      </nav>
    </aside>
  );
}

function NavLink({
  item,
  pathname,
  collapsed,
}: {
  item: NavItem;
  pathname: string;
  collapsed: boolean;
}) {
  const Icon = item.icon;
  const active =
    item.href === '/' ? pathname === '/' : pathname === item.href || pathname.startsWith(`${item.href}/`);

  return (
    <Link
      href={item.href}
      className={cn(
        'flex items-center gap-2 rounded-md px-3 py-2 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground',
        active && 'bg-accent text-foreground',
        collapsed && 'justify-center px-0',
      )}
      aria-current={active ? 'page' : undefined}
      title={collapsed ? item.label : undefined}
    >
      <Icon className="h-4 w-4 shrink-0" />
      {!collapsed && <span>{item.label}</span>}
    </Link>
  );
}
