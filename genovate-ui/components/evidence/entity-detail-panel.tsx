'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { LoadingSpinner } from '@/components/common/loading-spinner';
import { useEvidenceEdges, useEvidenceEntity } from '@/lib/hooks/use-evidence-graph';
import { entityColor } from '@/lib/utils/colors';
import { titleCase } from '@/lib/utils/formatters';
import { ConfidenceBadge } from '@/lib/utils/confidence-badge';

export function EntityDetailPanel({ entityId }: { entityId: string | null }) {
  const entity = useEvidenceEntity(entityId);
  const edges = useEvidenceEdges(entityId);

  if (!entityId) {
    return (
      <Card>
        <CardContent className="p-6 text-sm text-muted-foreground">
          Select an entity to view details.
        </CardContent>
      </Card>
    );
  }

  if (entity.isLoading) return <LoadingSpinner />;
  if (!entity.data) return null;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <span
            className="inline-block h-2.5 w-2.5 rounded-full"
            style={{ backgroundColor: entityColor(entity.data.entity_type) }}
          />
          <CardTitle className="text-base">{entity.data.name}</CardTitle>
        </div>
        <div className="text-xs uppercase tracking-wider text-muted-foreground">
          {titleCase(entity.data.entity_type)}
        </div>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        {entity.data.description && (
          <p className="text-muted-foreground">{entity.data.description}</p>
        )}

        <div>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Edges ({edges.data?.length ?? 0})
          </h4>
          <ul className="space-y-1">
            {edges.data?.map((e) => (
              <li
                key={e.id}
                className="flex items-center justify-between rounded-md border px-2 py-1"
              >
                <span className="truncate">
                  <span className="font-medium">{e.relation}</span> →{' '}
                  <span className="text-muted-foreground">{e.target_id}</span>
                </span>
                <ConfidenceBadge confidence={e.confidence} />
              </li>
            ))}
            {edges.data && edges.data.length === 0 && (
              <li className="text-xs text-muted-foreground">No edges.</li>
            )}
          </ul>
        </div>
      </CardContent>
    </Card>
  );
}
