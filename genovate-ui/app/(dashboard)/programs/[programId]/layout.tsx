'use client';

import { use, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useProgram } from '@/lib/hooks/use-programs';
import { useProgramStore } from '@/lib/stores/program-store';
import { LoadingSpinner } from '@/components/common/loading-spinner';
import { cn } from '@/lib/utils/cn';

const TABS = [
  { href: 'overview', label: 'Overview' },
  { href: 'evidence', label: 'Evidence' },
  { href: 'hypotheses', label: 'Hypotheses' },
  { href: 'candidates', label: 'Candidates' },
  { href: 'agents', label: 'Agents' },
  { href: 'guardian', label: 'Guardian' },
  { href: 'simulations', label: 'Simulations' },
];

export default function ProgramLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ programId: string }>;
}) {
  const { programId } = use(params);
  const pathname = usePathname();
  const setCurrentProgramId = useProgramStore((s) => s.setCurrentProgramId);
  const program = useProgram(programId);

  useEffect(() => {
    setCurrentProgramId(programId);
  }, [programId, setCurrentProgramId]);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          {program.data?.name ?? 'Program'}
        </h1>
        <p className="text-sm text-muted-foreground">
          {program.data?.therapeutic_area ?? '—'}
        </p>
      </div>

      <nav className="flex gap-1 overflow-x-auto border-b">
        {TABS.map((t) => {
          const href = `/programs/${programId}/${t.href}`;
          const active = pathname.startsWith(href);
          return (
            <Link
              key={t.href}
              href={href}
              className={cn(
                'whitespace-nowrap border-b-2 border-transparent px-3 py-2 text-sm text-muted-foreground hover:text-foreground',
                active && 'border-primary text-foreground',
              )}
            >
              {t.label}
            </Link>
          );
        })}
      </nav>

      {program.isLoading ? <LoadingSpinner /> : children}
    </div>
  );
}
