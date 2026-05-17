import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ConfidenceBadge } from '@/lib/utils/confidence-badge';
import { formatDateTime, titleCase } from '@/lib/utils/formatters';
import type { AgentRun } from '@/lib/types/genovate';

export function AgentOutputCard({ run }: { run: AgentRun }) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-base">{run.agent_name}</CardTitle>
          <ConfidenceBadge confidence={run.confidence} />
        </div>
        <div className="text-xs text-muted-foreground">
          {titleCase(run.run_type)} · {formatDateTime(run.started_at)}
        </div>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <p>{run.output_summary}</p>
        {run.uncertainty_reason && (
          <div className="rounded-md border border-confidence-medium/40 bg-confidence-medium/5 p-3">
            <p className="text-xs font-semibold uppercase tracking-wider text-confidence-medium">
              Uncertainty
            </p>
            <p className="mt-1">{run.uncertainty_reason}</p>
          </div>
        )}
        {run.recommended_next_step && (
          <div className="rounded-md border bg-muted/40 p-3">
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Recommended next step
            </p>
            <p className="mt-1">{run.recommended_next_step}</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
