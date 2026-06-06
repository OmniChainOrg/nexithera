'use client';

import { Card, CardContent } from '@/components/ui/card';
import { ExperimentKanban } from '@/components/experiments/experiment-kanban';
import { useNextExperiments } from '@/lib/hooks/use-analysis';
import { useProgramStore } from '@/lib/stores/program-store';

export default function ExperimentsPage() {
  const programId = useProgramStore((s) => s.currentProgramId);
  const { data = [] } = useNextExperiments(programId ? { program_id: programId, limit: 50 } : null);
  if (!programId) return <Card><CardContent className="p-6 text-sm text-muted-foreground">Select a program to view experiments.</CardContent></Card>;
  return <div className="space-y-4"><div><h1 className="text-xl font-semibold">Active learning experiments</h1><p className="text-sm text-muted-foreground">Prioritize, run, and record next best experiments.</p></div><ExperimentKanban experiments={data} programId={programId} /></div>;
}
