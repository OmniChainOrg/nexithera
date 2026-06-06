'use client';

import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { EvidenceGap } from '@/lib/types/genovate';

export function GapDetailPanel({ gap }: { gap: EvidenceGap | null }) {
  const router = useRouter();
  if (!gap) return <Card><CardContent className="p-6 text-sm text-muted-foreground">Select a heatmap cell to inspect evidence gaps.</CardContent></Card>;
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">Gap details</CardTitle></CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div><span className="text-muted-foreground">Target:</span> {gap.target_name}</div>
        <div><span className="text-muted-foreground">Disease:</span> {gap.disease_name}</div>
        <div className="flex gap-2"><Badge variant="outline">{gap.gap_type}</Badge><Badge variant={gap.severity >= 0.7 ? 'destructive' : 'secondary'}>Severity {gap.severity.toFixed(2)}</Badge></div>
        <div><span className="text-muted-foreground">Evidence quality:</span> {gap.evidence_quality.toFixed(2)}</div>
        {gap.proposed_experiment_id && <div><span className="text-muted-foreground">Proposed experiment:</span> {gap.proposed_experiment_id}</div>}
        {gap.details && <p className="text-muted-foreground">{gap.details}</p>}
        <Button
          onClick={() => {
            // TODO: Prefill the experiment scheduler once the experiments route accepts draft input.
            router.push(`/experiments?gap=${encodeURIComponent(gap.id ?? `${gap.target_id}-${gap.disease_id}`)}`);
          }}
        >
          Schedule experiment
        </Button>
      </CardContent>
    </Card>
  );
}
