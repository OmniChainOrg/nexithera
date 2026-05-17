'use client';

import { useState } from 'react';
import { EvidenceGraphView } from '@/components/evidence/evidence-graph';
import { EntityDetailPanel } from '@/components/evidence/entity-detail-panel';
import { Input } from '@/components/ui/input';
import { LoadingSpinner } from '@/components/common/loading-spinner';
import { EmptyState } from '@/components/common/empty-state';
import { useEvidenceGraph } from '@/lib/hooks/use-evidence-graph';
import { useProgramStore } from '@/lib/stores/program-store';

export default function GlobalEvidenceGraphPage() {
  const programId = useProgramStore((s) => s.currentProgramId);
  const { data, isLoading } = useEvidenceGraph(programId);
  const [selected, setSelected] = useState<string | null>(null);
  const [search, setSearch] = useState('');

  if (!programId) {
    return <EmptyState title="Select a program" description="Pick a program from the header." />;
  }
  if (isLoading) return <LoadingSpinner />;
  if (!data || !data.entities.length) {
    return <EmptyState title="No evidence yet" />;
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
      <div className="space-y-3">
        <Input
          placeholder="Search entities…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Search entities"
        />
        <EvidenceGraphView graph={data} onSelectEntity={setSelected} search={search} />
      </div>
      <EntityDetailPanel entityId={selected} />
    </div>
  );
}
