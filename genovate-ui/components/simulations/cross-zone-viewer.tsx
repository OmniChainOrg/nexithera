import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { formatRelative, titleCase } from '@/lib/utils/formatters';
import type { SimulationRun, SimulationRunStatus } from '@/lib/types/genovate';

const variant: Record<SimulationRunStatus, 'default' | 'secondary' | 'destructive' | 'outline'> = {
  queued: 'outline',
  running: 'secondary',
  completed: 'default',
  failed: 'destructive',
};

export function CrossZoneViewer({ runs }: { runs: SimulationRun[] }) {
  if (!runs.length) {
    return (
      <p className="p-4 text-center text-sm text-muted-foreground">No cross-zone runs yet.</p>
    );
  }
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {runs.map((r) => (
        <Card key={r.id}>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-medium">{titleCase(r.pipeline)}</CardTitle>
              <Badge variant={variant[r.status]}>{r.status}</Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-1 text-xs text-muted-foreground">
            <div>Started {formatRelative(r.started_at)}</div>
            {r.progress !== undefined && (
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full bg-primary"
                  style={{ width: `${Math.round(r.progress * 100)}%` }}
                />
              </div>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
