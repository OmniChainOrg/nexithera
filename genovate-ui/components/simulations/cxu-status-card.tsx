import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import type { CXU, CXUStatus } from '@/lib/types/genovate';

const statusVariant: Record<CXUStatus, 'default' | 'secondary' | 'destructive' | 'outline'> = {
  idle: 'outline',
  running: 'default',
  paused: 'secondary',
  terminated: 'outline',
  failed: 'destructive',
};

export function CXUStatusCard({ cxu }: { cxu: CXU }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium">{cxu.name}</CardTitle>
          <Badge variant={statusVariant[cxu.status]}>{cxu.status}</Badge>
        </div>
        <div className="text-xs text-muted-foreground">Zone {cxu.zone_id}</div>
      </CardHeader>
      <CardContent className="space-y-2 text-xs">
        <div className="flex justify-between">
          <span className="text-muted-foreground">Iteration</span>
          <span className="font-mono">{cxu.iteration}</span>
        </div>
        {cxu.latest_output && (
          <p className="line-clamp-2 text-muted-foreground">{cxu.latest_output}</p>
        )}
        {cxu.metrics && (
          <div className="grid grid-cols-2 gap-1 pt-1">
            {Object.entries(cxu.metrics).map(([k, v]) => (
              <div key={k} className="flex justify-between">
                <span className="truncate text-muted-foreground">{k}</span>
                <span className="font-mono">{v.toFixed(2)}</span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
