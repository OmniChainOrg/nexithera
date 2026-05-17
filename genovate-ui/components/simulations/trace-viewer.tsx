'use client';

import { formatDateTime } from '@/lib/utils/formatters';

export interface TraceStep {
  step: number;
  description: string;
  timestamp: string;
}

interface TraceViewerProps {
  steps: TraceStep[];
  /** Optional verification URL from EpistemicOS. */
  verifyUrl?: string;
}

export function TraceViewer({ steps, verifyUrl }: TraceViewerProps) {
  if (!steps.length) {
    return <p className="text-sm text-muted-foreground">No trace steps available.</p>;
  }
  return (
    <div className="space-y-2">
      {verifyUrl && (
        <a
          href={verifyUrl}
          target="_blank"
          rel="noreferrer noopener"
          className="text-xs text-primary hover:underline"
        >
          Verify trace on EpistemicOS →
        </a>
      )}
      <ol className="relative space-y-2 border-l pl-4">
        {steps.map((s) => (
          <li key={s.step}>
            <span className="absolute -left-[1.25rem] mt-1.5 h-2 w-2 rounded-full bg-primary" />
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span className="font-mono">#{s.step}</span>
              <span>{formatDateTime(s.timestamp)}</span>
            </div>
            <p className="text-sm">{s.description}</p>
          </li>
        ))}
      </ol>
    </div>
  );
}
