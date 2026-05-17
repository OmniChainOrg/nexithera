'use client';

import { useMemo, useState } from 'react';
import { CandidateCard } from './candidate-card';
import { candidateStatusBg, candidateStatusOrder } from '@/lib/utils/colors';
import { titleCase } from '@/lib/utils/formatters';
import { useUpdateCandidateStatus } from '@/lib/hooks/use-candidates';
import type { Candidate, CandidateStatus } from '@/lib/types/genovate';
import { cn } from '@/lib/utils/cn';

interface CandidateKanbanProps {
  programId: string;
  candidates: Candidate[];
}

/**
 * HTML5 drag-and-drop kanban for the candidate pipeline.
 *
 * Drops trigger a `PATCH /candidates/:id/status` mutation. Certain transitions
 * (e.g., promoted/killed) require Guardian approval at the API layer — the UI
 * surfaces any error returned by the backend.
 */
export function CandidateKanban({ programId, candidates }: CandidateKanbanProps) {
  const updateStatus = useUpdateCandidateStatus(programId);
  const [dragId, setDragId] = useState<string | null>(null);

  const grouped = useMemo(() => {
    const map = new Map<CandidateStatus, Candidate[]>();
    candidateStatusOrder.forEach((s) => map.set(s, []));
    for (const c of candidates) {
      const bucket = map.get(c.status) ?? [];
      bucket.push(c);
      map.set(c.status, bucket);
    }
    return map;
  }, [candidates]);

  return (
    <div
      className="flex gap-3 overflow-x-auto pb-3"
      role="list"
      aria-label="Candidate pipeline kanban"
    >
      {candidateStatusOrder.map((status) => {
        const items = grouped.get(status) ?? [];
        return (
          <div
            key={status}
            role="listitem"
            className={cn(
              'flex w-72 shrink-0 flex-col rounded-lg border bg-muted/30 p-2',
              dragId && 'ring-1 ring-primary/30',
            )}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              const id = e.dataTransfer.getData('text/plain');
              if (!id) return;
              updateStatus.mutate({ id, input: { status } });
              setDragId(null);
            }}
          >
            <div className="mb-2 flex items-center gap-2 px-1">
              <span
                className={cn('h-2 w-2 rounded-full', candidateStatusBg[status])}
                aria-hidden
              />
              <h3 className="text-xs font-semibold uppercase tracking-wider">
                {titleCase(status)}
              </h3>
              <span className="ml-auto text-xs text-muted-foreground">{items.length}</span>
            </div>
            <div className="flex flex-col gap-2">
              {items.map((c) => (
                <div
                  key={c.id}
                  draggable
                  onDragStart={(e) => {
                    e.dataTransfer.setData('text/plain', c.id);
                    setDragId(c.id);
                  }}
                  onDragEnd={() => setDragId(null)}
                >
                  <CandidateCard candidate={c} />
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
