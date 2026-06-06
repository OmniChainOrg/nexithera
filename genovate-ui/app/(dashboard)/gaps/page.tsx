'use client';

import { useState } from 'react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { GapDetailPanel } from '@/components/gaps/gap-detail-panel';
import { GapExportButton } from '@/components/gaps/gap-export-button';
import { GapHeatmap } from '@/components/gaps/gap-heatmap';
import { useGapAnalysis } from '@/lib/hooks/use-analysis';
import { usePrograms } from '@/lib/hooks/use-programs';
import { useProgramStore } from '@/lib/stores/program-store';
import type { EvidenceGap } from '@/lib/types/genovate';

export default function GapsPage() {
  const currentProgramId = useProgramStore((s) => s.currentProgramId);
  const setCurrentProgramId = useProgramStore((s) => s.setCurrentProgramId);
  const { data: programs = [] } = usePrograms();
  const [severity, setSeverity] = useState(0.5);
  const [selected, setSelected] = useState<EvidenceGap | null>(null);
  const { data } = useGapAnalysis(currentProgramId ? { program_id: currentProgramId, min_severity: 0 } : null);
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3"><div><h1 className="text-xl font-semibold">Evidence gaps</h1><p className="text-sm text-muted-foreground">Target–disease evidence quality matrix.</p></div><GapExportButton targets={data?.targets ?? []} diseases={data?.diseases ?? []} gaps={data?.gaps ?? []} /></div>
      <div className="flex flex-wrap items-center gap-3 rounded-lg border p-3"><Select value={currentProgramId ?? ''} onValueChange={setCurrentProgramId}><SelectTrigger className="w-64"><SelectValue placeholder="Select program" /></SelectTrigger><SelectContent>{programs.map((p) => <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>)}</SelectContent></Select><label className="flex items-center gap-2 text-sm">Min severity <Input type="range" min={0} max={1} step={0.05} value={severity} onChange={(e) => setSeverity(Number(e.target.value))} className="w-48" /> {severity.toFixed(2)}</label></div>
      <div className="grid gap-4 xl:grid-cols-[1fr_22rem]"><GapHeatmap targets={data?.targets ?? []} diseases={data?.diseases ?? []} gaps={data?.gaps ?? []} severityFilter={severity} onCellClick={setSelected} /><GapDetailPanel gap={selected} /></div>
    </div>
  );
}
