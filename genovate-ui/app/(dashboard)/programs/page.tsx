'use client';

import { LoadingSpinner } from '@/components/common/loading-spinner';
import { EmptyState } from '@/components/common/empty-state';
import { ProgramCard } from '@/components/programs/program-card';
import { CreateProgramDialog } from '@/components/programs/create-program-dialog';
import { usePrograms } from '@/lib/hooks/use-programs';

export default function ProgramsPage() {
  const { data, isLoading, isError, error } = usePrograms();

  if (isLoading) return <LoadingSpinner />;
  if (isError) {
    return <EmptyState title="Could not load programs" description={(error as Error).message} />;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Programs</h1>
        <CreateProgramDialog />
      </div>

      {data?.length ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {data.map((p) => (
            <ProgramCard key={p.id} program={p} />
          ))}
        </div>
      ) : (
        <EmptyState title="No programs" action={<CreateProgramDialog />} />
      )}
    </div>
  );
}
