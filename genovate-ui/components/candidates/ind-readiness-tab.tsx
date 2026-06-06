'use client';

import { useEffect, useMemo, useState } from 'react';
import { RefreshCw, ShieldAlert, Clock, FileWarning } from 'lucide-react';
import toast from 'react-hot-toast';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Tooltip } from '@/components/ui/tooltip';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { LoadingSpinner } from '@/components/common/loading-spinner';
import { EmptyState } from '@/components/common/empty-state';
import {
  useINDReadiness,
  useUpdateINDChecklistItem,
} from '@/lib/hooks/use-partnerability';
import { useProgramEvents } from '@/lib/hooks/use-websocket';
import { calculateINDProgress } from '@/lib/utils/ind-progress';
import type {
  INDChecklistItem,
  INDStatus,
} from '@/lib/api/partnerability';
import { cn } from '@/lib/utils/cn';

const STATUS_OPTIONS: { value: INDStatus; label: string }[] = [
  { value: 'not_started', label: 'Not Started' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'complete', label: 'Complete' },
  { value: 'waived', label: 'Waived' },
  { value: 'failed', label: 'Failed' },
];

const CATEGORY_COLOR: Record<string, string> = {
  CMC: 'bg-blue-100 text-blue-700',
  nonclinical_tox: 'bg-purple-100 text-purple-700',
  clinical_protocol: 'bg-emerald-100 text-emerald-700',
  regulatory: 'bg-amber-100 text-amber-700',
  gmp: 'bg-rose-100 text-rose-700',
};

interface INDReadinessTabProps {
  candidateId: string;
  /** Program id used to subscribe to the WS channel for live updates. */
  programId?: string;
}

export function INDReadinessTab({ candidateId, programId }: INDReadinessTabProps) {
  const { data, isLoading, isFetching, refetch, refresh } = useINDReadinessWithRefresh(
    candidateId,
    programId,
  );
  const mutation = useUpdateINDChecklistItem(candidateId);

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <LoadingSpinner />
      </div>
    );
  }
  if (!data) {
    return (
      <EmptyState
        title="No IND readiness data"
        description="Run IND readiness analysis first."
        action={
          <Button onClick={() => refetch()} variant="outline">
            <RefreshCw className="mr-2 h-4 w-4" /> Retry
          </Button>
        }
      />
    );
  }

  const progress = calculateINDProgress(data);
  const items = data.items ?? [];

  const indicatorClass =
    progress.level === 'green'
      ? 'bg-emerald-500'
      : progress.level === 'yellow'
      ? 'bg-amber-500'
      : 'bg-red-500';

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold">IND Readiness</h2>
        <Button variant="outline" size="sm" onClick={refresh} disabled={isFetching}>
          <RefreshCw className={cn('mr-2 h-4 w-4', isFetching && 'animate-spin')} />
          Refresh
        </Button>
      </div>

      <Card>
        <CardContent className="space-y-3 p-4">
          <div className="flex items-center justify-between text-sm">
            <span className="font-medium">
              {progress.complete} / {progress.total} items complete
            </span>
            <span className="font-bold">{progress.percentage}%</span>
          </div>
          <Progress value={progress.percentage} indicatorClassName={indicatorClass} />
          <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
            {progress.estimatedTimelineMonths != null && (
              <span className="inline-flex items-center gap-1">
                <Clock className="h-3.5 w-3.5" /> Estimated time to IND:{' '}
                <strong>{progress.estimatedTimelineMonths} months</strong>
              </span>
            )}
            <span className="inline-flex items-center gap-1">
              <ShieldAlert className="h-3.5 w-3.5" /> Critical gaps:{' '}
              <strong>{progress.criticalGaps.length}</strong>
            </span>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Checklist</CardTitle>
        </CardHeader>
        <CardContent>
          {items.length === 0 ? (
            <EmptyState
              title="No checklist items"
              description="The agent has not produced an IND checklist yet."
            />
          ) : (
            <ChecklistTable
              items={items}
              isUpdating={mutation.isPending}
              onChangeStatus={(item, status) => {
                mutation.mutate(
                  { itemId: item.item_id, input: { status } },
                  {
                    onError: () => toast.error('Failed to update checklist item'),
                  },
                );
              }}
            />
          )}
        </CardContent>
      </Card>

      <CriticalPathSection candidateId={candidateId} items={progress.criticalGaps} />
    </div>
  );
}

// ============================================================
// Checklist table
// ============================================================

function ChecklistTable({
  items,
  isUpdating,
  onChangeStatus,
}: {
  items: INDChecklistItem[];
  isUpdating: boolean;
  onChangeStatus: (item: INDChecklistItem, status: INDStatus) => void;
}) {
  const sorted = useMemo(
    () => items.slice().sort((a, b) => a.category.localeCompare(b.category)),
    [items],
  );

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[760px] text-sm">
        <thead className="border-b text-left text-xs uppercase text-muted-foreground">
          <tr>
            <th className="px-2 py-2">Item</th>
            <th className="px-2 py-2">Category</th>
            <th className="px-2 py-2">Status</th>
            <th className="px-2 py-2">Evidence</th>
            <th className="px-2 py-2">Notes</th>
            <th className="px-2 py-2">Actions</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((item) => (
            <tr
              key={item.item_id}
              className={cn(
                'border-b last:border-0 hover:bg-muted/40',
                isUpdating && 'animate-pulse',
              )}
            >
              <td className="px-2 py-2">
                <Tooltip content={item.description ?? ''}>
                  <span className="font-medium">{item.item}</span>
                </Tooltip>
                {item.is_required && (
                  <span className="ml-1 text-xs text-red-500">*</span>
                )}
              </td>
              <td className="px-2 py-2">
                <Badge
                  className={cn(
                    'text-[10px]',
                    CATEGORY_COLOR[item.category] ?? 'bg-gray-100 text-gray-700',
                  )}
                  variant="outline"
                >
                  {item.category}
                </Badge>
              </td>
              <td className="px-2 py-2">
                <Select
                  value={item.status}
                  onValueChange={(v) => onChangeStatus(item, v as INDStatus)}
                >
                  <SelectTrigger className="h-8 w-36">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {STATUS_OPTIONS.map((s) => (
                      <SelectItem key={s.value} value={s.value}>
                        {s.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </td>
              <td className="px-2 py-2">
                {item.evidence_uri ? (
                  <a
                    href={item.evidence_uri}
                    target="_blank"
                    rel="noreferrer"
                    className="text-primary underline"
                  >
                    Link
                  </a>
                ) : (
                  <span className="text-xs text-muted-foreground">—</span>
                )}
              </td>
              <td className="px-2 py-2">
                {item.notes ? (
                  <Tooltip content={item.notes}>
                    <FileWarning className="h-4 w-4 text-muted-foreground" />
                  </Tooltip>
                ) : (
                  <span className="text-xs text-muted-foreground">—</span>
                )}
              </td>
              <td className="px-2 py-2">
                {item.status === 'failed' && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => toast('Guardian review requested')}
                  >
                    Request Review
                  </Button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ============================================================
// Critical Path
// ============================================================

function CriticalPathSection({
  candidateId,
  items,
}: {
  candidateId: string;
  items: INDChecklistItem[];
}) {
  if (items.length === 0) {
    return (
      <Card>
        <CardContent className="p-6 text-sm text-emerald-600">
          ✅ No critical path gaps — all required items are on track.
        </CardContent>
      </Card>
    );
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">🚨 Critical Path Gaps (Blocking IND)</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-3 md:grid-cols-2">
        {items.map((it) => (
          <div key={it.item_id} className="rounded-lg border border-red-200 bg-red-50/40 p-3">
            <p className="font-semibold">{it.item}</p>
            {it.description && (
              <p className="mt-1 text-xs text-muted-foreground">{it.description}</p>
            )}
            <div className="mt-2 flex items-center justify-between text-xs">
              <Badge variant="outline">{it.category}</Badge>
              <Button
                size="sm"
                variant="outline"
                onClick={() => toast(`Task created for ${candidateId}`)}
              >
                Create Task
              </Button>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

// ============================================================
// Hook combining query + WS push refresh
// ============================================================

function useINDReadinessWithRefresh(candidateId: string, programId?: string) {
  const query = useINDReadiness(candidateId);

  // Subscribe to the program-level channel so the IND readiness tab is
  // refreshed when the agent publishes `ind_readiness.updated`. The shared
  // `ProgramEventsListener` already invalidates many caches, but we also
  // listen directly here so the dependency is explicit.
  const stream = useProgramEvents(programId ?? null, { enabled: !!programId });

  useEffect(() => {
    const msg = stream.lastMessage;
    if (!msg) return;
    if (msg.event_type === 'ind_readiness.updated' && msg.entity_id === candidateId) {
      query.refetch();
    }
  }, [stream.lastMessage, candidateId, query]);

  return {
    ...query,
    refresh: () => query.refetch(),
  };
}
