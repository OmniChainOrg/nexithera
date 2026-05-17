import { ConfidenceBadge } from '@/lib/utils/confidence-badge';
import type { EvidenceEdge } from '@/lib/types/genovate';

export function EvidenceEdgeList({ edges }: { edges: EvidenceEdge[] }) {
  return (
    <ul className="divide-y rounded-lg border">
      {edges.map((e) => (
        <li key={e.id} className="flex items-center justify-between gap-3 px-3 py-2 text-sm">
          <div className="min-w-0">
            <div className="truncate font-medium">{e.relation}</div>
            <div className="truncate text-xs text-muted-foreground">
              {e.source_id} → {e.target_id}
            </div>
          </div>
          <ConfidenceBadge confidence={e.confidence} />
        </li>
      ))}
      {edges.length === 0 && (
        <li className="p-4 text-center text-sm text-muted-foreground">No edges to display.</li>
      )}
    </ul>
  );
}
