'use client';

import { qualityToColor } from '@/lib/utils/heatmap';
import type { EvidenceGap } from '@/lib/types/genovate';

export { qualityToColor };

export function GapHeatmap({
  targets,
  diseases,
  gaps,
  severityFilter,
  onCellClick,
}: {
  targets: { id: string; name: string }[];
  diseases: { id: string; name: string }[];
  gaps: EvidenceGap[];
  severityFilter: number;
  onCellClick: (gap: EvidenceGap) => void;
}) {
  const filtered = gaps.filter((g) => g.severity >= severityFilter);
  const byCell = new Map(filtered.map((g) => [`${g.target_id}:${g.disease_id}`, g]));
  if (!targets.length || !diseases.length) return <div className="rounded-lg border p-8 text-center text-sm text-muted-foreground">No gap matrix data.</div>;

  return (
    <div className="overflow-auto rounded-lg border" data-gap-heatmap>
      <div className="grid min-w-[720px]" style={{ gridTemplateColumns: `12rem repeat(${diseases.length}, minmax(5rem, 1fr))` }}>
        <div className="sticky left-0 z-10 bg-card p-2 text-xs font-medium">Target / Disease</div>
        {diseases.map((d) => <div key={d.id} className="border-l p-2 text-xs font-medium text-muted-foreground">{d.name}</div>)}
        {targets.map((target) => [
          <div key={`${target.id}-label`} className="sticky left-0 z-10 border-t bg-card p-2 text-sm font-medium">{target.name}</div>,
          ...diseases.map((disease) => {
            const gap = byCell.get(`${target.id}:${disease.id}`);
            const quality = gap?.evidence_quality ?? 0;
            return (
              <button
                key={`${target.id}-${disease.id}`}
                type="button"
                onClick={() => gap && onCellClick(gap)}
                disabled={!gap}
                className="min-h-16 border-l border-t p-2 text-center text-xs disabled:cursor-not-allowed disabled:opacity-40"
                style={{ backgroundColor: qualityToColor(quality) }}
                title={gap ? `${gap.gap_type}: severity ${gap.severity}` : 'No gap'}
              >
                {gap ? quality.toFixed(2) : '—'}
              </button>
            );
          }),
        ])}
      </div>
    </div>
  );
}
