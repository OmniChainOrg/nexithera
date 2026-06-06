'use client';

import { useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { RefreshCw } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { CreateCandidateFromTargetDialog } from '@/components/target-discovery/create-candidate-from-target-dialog';
import { TargetDiscoveryTable } from '@/components/target-discovery/target-discovery-table';
import { useDiscoverTargets } from '@/lib/hooks/use-target-discovery';
import { queryKeys } from '@/lib/hooks/query-keys';
import { useProgram } from '@/lib/hooks/use-programs';
import { useProgramStore } from '@/lib/stores/program-store';
import { useWebSocketStore } from '@/lib/stores/websocket-store';
import type { DiscoverTargetsResponse, DiscoveredTarget } from '@/lib/types/genovate';

export default function TargetDiscoveryPage() {
  const programId = useProgramStore((s) => s.currentProgramId);
  const { data: program } = useProgram(programId);
  const qc = useQueryClient();
  const [selected, setSelected] = useState<DiscoveredTarget | null>(null);
  const [candidateTarget, setCandidateTarget] = useState<DiscoveredTarget | null>(null);
  const discover = useDiscoverTargets(programId);
  const cached = programId ? qc.getQueryData<DiscoverTargetsResponse>(queryKeys.targets.discover(programId)) : undefined;
  const targets = discover.data?.targets ?? cached?.targets ?? [];
  const notifications = useWebSocketStore((s) => s.notifications);
  const newCount = useMemo(() => notifications.filter((n) => n.programId === programId && n.title.toLowerCase().includes('target')).length, [notifications, programId]);

  function refresh() {
    if (programId) discover.mutate({ program_id: programId, max_results: 25, therapeutic_area: program?.therapeutic_area });
  }

  if (!programId) return <Card><CardContent className="p-6 text-sm text-muted-foreground">Select a program to discover targets.</CardContent></Card>;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between"><div><h1 className="text-xl font-semibold">Target discovery</h1><p className="text-sm text-muted-foreground">Ranked target opportunities for {program?.name ?? 'the current program'}.</p></div><div className="flex gap-2"><Badge variant="secondary">{newCount} new</Badge><Button onClick={refresh} disabled={discover.isPending}><RefreshCw className="h-4 w-4" />Refresh</Button></div></div>
      <div className="grid gap-4 xl:grid-cols-[1fr_22rem]">
        <TargetDiscoveryTable targets={targets} selectedId={selected?.id ?? selected?.target_id} onSelect={setSelected} onCreateCandidate={setCandidateTarget} />
        <Card><CardHeader><CardTitle className="text-base">Target details</CardTitle></CardHeader><CardContent className="space-y-2 text-sm">{selected ? <><div className="font-medium">{selected.target_name}</div><div>Opportunity: {Math.round(selected.opportunity_score * 100)}%</div><p className="text-muted-foreground">{selected.rationale ?? selected.proposed_hypothesis}</p><Button onClick={() => setCandidateTarget(selected)}>Create Candidate</Button></> : <p className="text-muted-foreground">Select a target to see rationale.</p>}</CardContent></Card>
      </div>
      <CreateCandidateFromTargetDialog target={candidateTarget} programId={programId} therapeuticArea={program?.therapeutic_area} open={!!candidateTarget} onOpenChange={(o) => !o && setCandidateTarget(null)} />
    </div>
  );
}
