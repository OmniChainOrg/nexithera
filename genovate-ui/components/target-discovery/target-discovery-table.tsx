'use client';

import { useMemo } from 'react';
import { createColumnHelper, flexRender, getCoreRowModel, useReactTable } from '@tanstack/react-table';
import { Button } from '@/components/ui/button';
import { ConfidenceBadge } from '@/lib/utils/confidence-badge';
import type { DiscoveredTarget } from '@/lib/types/genovate';

const helper = createColumnHelper<DiscoveredTarget>();

export function TargetDiscoveryTable({
  targets,
  selectedId,
  onSelect,
  onCreateCandidate,
}: {
  targets: DiscoveredTarget[];
  selectedId?: string;
  onSelect: (target: DiscoveredTarget) => void;
  onCreateCandidate: (target: DiscoveredTarget) => void;
}) {
  const columns = useMemo(() => [
    helper.accessor('rank', { header: 'Rank', cell: (info) => <span className="font-mono">#{info.getValue()}</span> }),
    helper.accessor('target_name', {
      header: 'Target name',
      cell: (info) => (
        <button type="button" className="font-medium text-primary hover:underline" onClick={() => onSelect(info.row.original)}>
          {info.getValue()}
        </button>
      ),
    }),
    helper.accessor('opportunity_score', {
      header: 'Opportunity score',
      cell: (info) => {
        const pct = Math.round(info.getValue() * 100);
        return <div className="min-w-28"><div className="mb-1 text-xs font-medium">{pct}%</div><div className="h-2 rounded-full bg-muted"><div className="h-2 rounded-full bg-primary" style={{ width: `${pct}%` }} /></div></div>;
      },
    }),
    helper.accessor('confidence', { header: 'Confidence', cell: (info) => <ConfidenceBadge confidence={info.getValue()} /> }),
    helper.accessor('proposed_hypothesis', { header: 'Hypothesis', cell: (info) => <span className="block max-w-xs truncate" title={info.getValue()}>{info.getValue()}</span> }),
    helper.display({ id: 'action', header: '', cell: (info) => <Button size="sm" onClick={() => onCreateCandidate(info.row.original)}>Create Candidate</Button> }),
  ], [onCreateCandidate, onSelect]);

  const table = useReactTable({ data: targets, columns, getCoreRowModel: getCoreRowModel() });
  if (!targets.length) return <div className="rounded-lg border p-8 text-center text-sm text-muted-foreground">No targets discovered yet.</div>;

  return (
    <div className="overflow-hidden rounded-lg border">
      <table className="w-full text-sm">
        <thead className="bg-muted/60 text-left">
          {table.getHeaderGroups().map((hg) => <tr key={hg.id}>{hg.headers.map((h) => <th key={h.id} className="px-3 py-2 font-medium">{h.isPlaceholder ? null : flexRender(h.column.columnDef.header, h.getContext())}</th>)}</tr>)}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => {
            const isSelected = selectedId && (row.original.id ?? row.original.target_id) === selectedId;
            return <tr key={row.id} className={isSelected ? 'bg-accent' : 'border-t'}>{row.getVisibleCells().map((cell) => <td key={cell.id} className="px-3 py-3 align-top">{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>)}</tr>;
          })}
        </tbody>
      </table>
    </div>
  );
}
