import { ConfidenceBadge } from '@/lib/utils/confidence-badge';
import { formatDateTime } from '@/lib/utils/formatters';
import type { HypothesisVersion } from '@/lib/types/genovate';

export function HypothesisVersionTimeline({ versions }: { versions: HypothesisVersion[] }) {
  if (!versions.length) {
    return <p className="text-sm text-muted-foreground">No version history.</p>;
  }
  return (
    <ol className="relative space-y-4 border-l pl-4">
      {versions.map((v) => (
        <li key={v.version} className="relative">
          <span className="absolute -left-[1.4rem] mt-1.5 h-2.5 w-2.5 rounded-full bg-primary" />
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span className="font-mono">v{v.version}</span>
            <span>{formatDateTime(v.created_at)}</span>
            {v.author && <span>· {v.author}</span>}
            <ConfidenceBadge confidence={v.confidence} />
          </div>
          <p className="mt-1 text-sm">{v.text}</p>
        </li>
      ))}
    </ol>
  );
}
