import Link from 'next/link';
import { Badge } from '@/components/ui/badge';
import { ConfidenceBadge } from '@/lib/utils/confidence-badge';
import { formatRelative, titleCase } from '@/lib/utils/formatters';
import type { AgentRun, AgentRunStatus } from '@/lib/types/genovate';

const statusVariant: Record<AgentRunStatus, 'default' | 'secondary' | 'destructive' | 'outline'> = {
  pending: 'outline',
  running: 'secondary',
  completed: 'default',
  failed: 'destructive',
};

interface AgentRunListProps {
  runs: AgentRun[];
  /** Optional link template, used by global pages. */
  hrefForRun?: (run: AgentRun) => string;
  /** Optional click handler, used to open the detail panel. */
  onRunClick?: (run: AgentRun) => void;
}

export function AgentRunList({ runs, hrefForRun, onRunClick }: AgentRunListProps) {
  if (!runs.length) {
    return <p className="p-6 text-center text-sm text-muted-foreground">No agent runs yet.</p>;
  }
  return (
    <div className="overflow-hidden rounded-lg border">
      <table className="w-full text-sm">
        <thead className="bg-muted/40 text-xs uppercase tracking-wider text-muted-foreground">
          <tr>
            <th className="px-3 py-2 text-left font-medium">Agent</th>
            <th className="px-3 py-2 text-left font-medium">Run type</th>
            <th className="px-3 py-2 text-left font-medium">Status</th>
            <th className="px-3 py-2 text-left font-medium">Confidence</th>
            <th className="px-3 py-2 text-left font-medium">Started</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {runs.map((r) => (
            <tr
              key={r.id}
              className={`hover:bg-accent/40${onRunClick ? ' cursor-pointer' : ''}`}
              onClick={onRunClick ? () => onRunClick(r) : undefined}
            >
              <td className="px-3 py-2 font-medium">
                {hrefForRun ? (
                  <Link href={hrefForRun(r)} className="hover:underline" onClick={(e) => e.stopPropagation()}>
                    {r.agent_name}
                  </Link>
                ) : (
                  r.agent_name
                )}
              </td>
              <td className="px-3 py-2 text-muted-foreground">{titleCase(r.run_type)}</td>
              <td className="px-3 py-2">
                <Badge variant={statusVariant[r.status]}>{r.status}</Badge>
              </td>
              <td className="px-3 py-2">
                <ConfidenceBadge confidence={r.confidence} />
              </td>
              <td className="px-3 py-2 text-muted-foreground">{formatRelative(r.started_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
