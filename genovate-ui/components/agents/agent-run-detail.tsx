'use client';

import { useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { ConfidenceBadge } from '@/lib/utils/confidence-badge';
import { formatRelative, titleCase } from '@/lib/utils/formatters';
import type { AgentRun, AgentRunStatus, AgentTraceStep } from '@/lib/types/genovate';

const statusVariant: Record<AgentRunStatus, 'default' | 'secondary' | 'destructive' | 'outline'> = {
  pending: 'outline',
  running: 'secondary',
  completed: 'default',
  failed: 'destructive',
};

interface AgentRunDetailProps {
  run: AgentRun | null;
  onClose: () => void;
}

function CollapsibleSection({
  title,
  children,
  defaultOpen = false,
}: {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="rounded-md border">
      <button
        type="button"
        className="flex w-full items-center justify-between px-4 py-2 text-sm font-medium hover:bg-accent/40"
        onClick={() => setOpen((v) => !v)}
      >
        <span>{title}</span>
        <span className="text-muted-foreground">{open ? '▲' : '▼'}</span>
      </button>
      {open && <div className="border-t px-4 py-3">{children}</div>}
    </div>
  );
}

function JsonViewer({ data }: { data: unknown }) {
  return (
    <pre className="overflow-auto rounded bg-muted p-3 text-xs leading-relaxed">
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}

function TraceStepRow({ step }: { step: AgentTraceStep }) {
  const kindVariant: Record<string, 'default' | 'secondary' | 'outline'> = {
    reasoning: 'secondary',
    tool_call: 'default',
    critique: 'outline',
  };
  return (
    <div className="flex gap-3 py-2 text-sm">
      <span className="w-6 shrink-0 text-right text-muted-foreground">{step.step}</span>
      <Badge variant={kindVariant[step.kind] ?? 'outline'} className="h-5 shrink-0 text-xs">
        {step.kind}
      </Badge>
      <span className="min-w-0 flex-1 break-words">{step.content}</span>
    </div>
  );
}

export function AgentRunDetail({ run, onClose }: AgentRunDetailProps) {
  if (!run) return null;

  const hasTrace = Array.isArray(run.trace) && run.trace.length > 0;
  const hasStructure =
    run.structured_output && Object.keys(run.structured_output).length > 0;

  return (
    <Dialog open={!!run} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-base">
            {run.agent_name}
            <Badge variant={statusVariant[run.status]}>{run.status}</Badge>
          </DialogTitle>
        </DialogHeader>

        {/* Meta row */}
        <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
          <span>
            <span className="font-medium text-foreground">Run type:</span>{' '}
            {titleCase(run.run_type)}
          </span>
          <span>
            <span className="font-medium text-foreground">Started:</span>{' '}
            {formatRelative(run.started_at)}
          </span>
          {run.completed_at && (
            <span>
              <span className="font-medium text-foreground">Completed:</span>{' '}
              {formatRelative(run.completed_at)}
            </span>
          )}
          <span>
            <span className="font-medium text-foreground">Confidence:</span>{' '}
            <ConfidenceBadge confidence={run.confidence} />
          </span>
        </div>

        {/* Summary */}
        {run.output_summary && (
          <div className="rounded-md bg-muted/40 px-4 py-3 text-sm">
            <p className="font-medium text-foreground">Summary</p>
            <p className="mt-1 text-muted-foreground">{run.output_summary}</p>
          </div>
        )}

        {/* Recommended next step */}
        {run.recommended_next_step && (
          <div className="rounded-md border border-primary/30 bg-primary/5 px-4 py-3 text-sm">
            <p className="font-medium text-primary">Recommended next step</p>
            <p className="mt-1">{run.recommended_next_step}</p>
          </div>
        )}

        {/* Uncertainty */}
        {run.uncertainty_reason && (
          <div className="rounded-md border border-yellow-300 bg-yellow-50 px-4 py-2 text-sm dark:border-yellow-700 dark:bg-yellow-950">
            <span className="font-medium">⚠ Uncertainty: </span>
            {run.uncertainty_reason}
          </div>
        )}

        <div className="space-y-2">
          {/* Trace */}
          {hasTrace && (
            <CollapsibleSection title={`Trace (${run.trace!.length} steps)`}>
              <div className="divide-y">
                {run.trace!.map((step, i) => (
                  <TraceStepRow key={i} step={step} />
                ))}
              </div>
            </CollapsibleSection>
          )}

          {/* Structured output */}
          {hasStructure && (
            <CollapsibleSection title="Structured output">
              <JsonViewer data={run.structured_output} />
            </CollapsibleSection>
          )}
        </div>

        <div className="flex justify-end pt-2">
          <Button variant="outline" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
