'use client';

import { useMemo, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Pause, Square, Play } from 'lucide-react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { simulationsApi } from '@/lib/api/simulations';
import { useCXUStream } from '@/lib/hooks/use-websocket';
import type { CXU } from '@/lib/types/genovate';

interface CXUMonitorProps {
  cxu: CXU;
}

/**
 * Live monitor for a single Cognitive eXperiment Unit (CXU).
 *
 * Combines:
 *  - Last-known REST snapshot (`cxu` prop)
 *  - Streaming `/ws/cxu/{id}` updates for iteration, metrics, and confidence
 *  - Pause / resume / terminate controls posted to the REST API
 */
export function CXUMonitor({ cxu }: CXUMonitorProps) {
  const stream = useCXUStream(cxu.id);
  const latest = stream.lastMessage;

  const pause = useMutation({ mutationFn: () => simulationsApi.pauseCXU(cxu.id) });
  const resume = useMutation({ mutationFn: () => simulationsApi.startCXU(cxu.id) });
  const terminate = useMutation({ mutationFn: () => simulationsApi.terminateCXU(cxu.id) });

  // Build the metrics chart from the last 50 streamed iterations.
  const series = useMemo(
    () =>
      stream.messages.slice(-50).map((m) => ({
        iteration: m.iteration,
        duration_ms: m.metrics.duration_ms,
        confidence: m.confidence ?? null,
      })),
    [stream.messages],
  );

  const isRunning = cxu.status === 'running' || stream.status === 'open';
  const [showRaw, setShowRaw] = useState(false);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-2">
          <div>
            <CardTitle className="text-base">{cxu.name}</CardTitle>
            <p className="text-xs text-muted-foreground">Zone {cxu.zone_id}</p>
          </div>
          <Badge variant={isRunning ? 'default' : 'outline'}>{cxu.status}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div className="grid grid-cols-3 gap-3">
          <Stat label="Iteration" value={String(latest?.iteration ?? cxu.iteration)} />
          <Stat
            label="Last duration"
            value={
              latest?.metrics.duration_ms != null
                ? `${latest.metrics.duration_ms.toFixed(0)} ms`
                : '—'
            }
          />
          <Stat
            label="Confidence"
            value={
              latest?.confidence != null ? `${(latest.confidence * 100).toFixed(0)}%` : '—'
            }
          />
        </div>

        <div className="h-32 w-full rounded-md border bg-card">
          {series.length === 0 ? (
            <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
              Waiting for live data…
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={series} margin={{ top: 8, right: 12, bottom: 4, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                <XAxis dataKey="iteration" fontSize={10} />
                <YAxis fontSize={10} />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="duration_ms"
                  stroke="#2563eb"
                  strokeWidth={1.5}
                  dot={false}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="flex flex-wrap gap-2">
          {cxu.status === 'paused' ? (
            <Button
              size="sm"
              onClick={() => resume.mutate()}
              disabled={resume.isPending}
            >
              <Play className="h-3.5 w-3.5" /> Resume
            </Button>
          ) : (
            <Button
              size="sm"
              variant="outline"
              onClick={() => pause.mutate()}
              disabled={pause.isPending || cxu.status !== 'running'}
            >
              <Pause className="h-3.5 w-3.5" /> Pause
            </Button>
          )}
          <Button
            size="sm"
            variant="destructive"
            onClick={() => terminate.mutate()}
            disabled={terminate.isPending || cxu.status === 'terminated'}
          >
            <Square className="h-3.5 w-3.5" /> Terminate
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setShowRaw((v) => !v)}
            className="ml-auto"
          >
            {showRaw ? 'Hide' : 'Show'} trace
          </Button>
        </div>

        {showRaw && latest && (
          <pre className="overflow-auto rounded-md border bg-muted/40 p-2 text-[10px]">
            {JSON.stringify(latest, null, 2)}
          </pre>
        )}

        {stream.error && (
          <p className="text-xs text-amber-600 dark:text-amber-400">
            Live stream unavailable: {stream.error}. Falling back to last snapshot.
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border bg-muted/30 px-2 py-1.5">
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className="font-mono text-sm">{value}</p>
    </div>
  );
}
