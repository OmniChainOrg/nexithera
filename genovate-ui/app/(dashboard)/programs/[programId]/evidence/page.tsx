'use client';

import { useState } from 'react';
import { EvidenceGraphView } from '@/components/evidence/evidence-graph';
import { EntityDetailPanel } from '@/components/evidence/entity-detail-panel';
import { LoadingSpinner } from '@/components/common/loading-spinner';
import { EmptyState } from '@/components/common/empty-state';
import { Input } from '@/components/ui/input';
import { useEvidenceGraph } from '@/lib/hooks/use-evidence-graph';

export default function EvidenceGraphPage({ params }: { params: { programId: string } }) {
  const { data, isLoading, isError } = useEvidenceGraph(params.programId);
  const [selected, setSelected] = useState<string | null>(null);
  const [search, setSearch] = useState('');

  if (isLoading) return <LoadingSpinner />;
  if (isError || !data) return <EmptyState title="Evidence graph unavailable" />;
  if (!data.entities.length) {
    return <EmptyState title="No evidence yet" description="Run agents to populate the graph." />;
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
      <div className="space-y-3">
        <Input
          placeholder="Search entities…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Search entities in graph"
        />
        <EvidenceGraphView graph={data} onSelectEntity={setSelected} search={search} />
      </div>
      <EntityDetailPanel entityId={selected} />
    </div>
  );
}
