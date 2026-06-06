'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { ExperimentCard } from '@/components/experiments/experiment-card';
import { ExperimentResultDialog } from '@/components/experiments/experiment-result-dialog';
import { useConductExperiment, useUpdateExperimentStatus } from '@/lib/hooks/use-analysis';
import type { ExperimentOutcome, ProposedExperiment, ProposedExperimentStatus } from '@/lib/types/genovate';

const columns: Array<{ status: ProposedExperimentStatus; title: string }> = [
  { status: 'proposed', title: 'Proposed' },
  { status: 'in_progress', title: 'In Progress' },
  { status: 'completed', title: 'Completed' },
];

export function ExperimentKanban({ experiments, programId }: { experiments: ProposedExperiment[]; programId: string }) {
  const [selected, setSelected] = useState<string[]>([]);
  const [active, setActive] = useState<ProposedExperiment | null>(null);
  const [readOnly, setReadOnly] = useState(false);
  const conduct = useConductExperiment(programId);
  const updateStatus = useUpdateExperimentStatus(programId);
  const toggle = (id: string, checked: boolean) => setSelected((prev) => checked ? [...prev, id] : prev.filter((x) => x !== id));
  const bulk = (status: ProposedExperimentStatus) => selected.forEach((id) => updateStatus.mutate({ id, status }));
  const submit = (outcome: ExperimentOutcome) => {
    conduct.mutate({ id: outcome.experiment_id, outcome });
    setActive(null);
  };
  return (
    <div className="space-y-4">
      <div className="flex gap-2"><Button variant="outline" disabled={!selected.length} onClick={() => bulk('in_progress')}>Schedule selected</Button><Button variant="outline" disabled={!selected.length} onClick={() => bulk('dismissed')}>Dismiss selected</Button></div>
      <div className="grid gap-4 lg:grid-cols-3">
        {columns.map((col) => <div key={col.status} className="space-y-3 rounded-lg border bg-muted/20 p-3"><h2 className="font-semibold">{col.title}</h2>{experiments.filter((e) => e.status === col.status).map((e) => <ExperimentCard key={e.id} experiment={e} selected={selected.includes(e.id)} onSelectedChange={(c) => toggle(e.id, c)} onConduct={() => { setReadOnly(false); setActive(e); }} onDismiss={() => updateStatus.mutate({ id: e.id, status: 'dismissed' })} onCancel={() => updateStatus.mutate({ id: e.id, status: 'cancelled' })} onComplete={() => { setReadOnly(false); setActive(e); }} onView={() => { setReadOnly(true); setActive(e); }} />)}</div>)}
      </div>
      <ExperimentResultDialog experiment={active} open={!!active} readOnly={readOnly} onOpenChange={(o) => !o && setActive(null)} onSubmit={submit} />
    </div>
  );
}
