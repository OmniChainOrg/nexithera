'use client';

import { useMemo } from 'react';
import { Wrench, MessageSquare } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ConfidenceGauge } from '@/components/agents/confidence-gauge';
import { useAgentRunStream } from '@/lib/hooks/use-websocket';
import type { AgentOutputMessage } from '@/lib/types/websocket';

interface LiveAgentRunProps {
  runId: string;
  agentName?: string;
}

/**
 * Streaming display for an in-flight agent run.
 *
 *  - Concatenates `chunk` messages into a typewriter-style output
 *  - Renders `tool_call` events as inline pills with arguments
 *  - Drives a circular confidence gauge from `confidence` updates
 *  - Surfaces a "Run complete" indicator on the terminal `complete` frame
 */
export function LiveAgentRun({ runId, agentName }: LiveAgentRunProps) {
  const stream = useAgentRunStream(runId);

  const { output, toolCalls, confidence, isComplete } = useMemo(() => {
    let outBuf = '';
    const tools: Array<{ name: string; args?: Record<string, unknown>; idx: number }> = [];
    let conf: number | null = null;
    let complete = false;
    stream.messages.forEach((m: AgentOutputMessage, idx) => {
      if (m.type === 'chunk' && m.content) outBuf += m.content;
      if (m.type === 'tool_call') tools.push({ name: m.tool_name ?? 'tool', args: m.tool_args, idx });
      if (m.type === 'confidence' && typeof m.confidence === 'number') conf = m.confidence;
      if (m.type === 'complete') {
        complete = true;
        if (typeof m.confidence === 'number') conf = m.confidence;
      }
    });
    return { output: outBuf, toolCalls: tools, confidence: conf, isComplete: complete };
  }, [stream.messages]);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-2">
          <div>
            <CardTitle className="text-base">
              {agentName ?? 'Agent run'}{' '}
              <span className="font-mono text-xs text-muted-foreground">{runId.slice(0, 8)}</span>
            </CardTitle>
            <p className="text-xs text-muted-foreground">
              Streaming {stream.status === 'open' ? 'live' : `(${stream.status})`}
            </p>
          </div>
          {isComplete ? <Badge variant="secondary">Complete</Badge> : <Badge>Running</Badge>}
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid gap-4 md:grid-cols-[1fr_auto]">
          <div className="space-y-3">
            <div
              className="min-h-[120px] whitespace-pre-wrap rounded-md border bg-muted/30 p-3 font-mono text-xs"
              aria-live="polite"
            >
              {output || (
                <span className="text-muted-foreground">
                  <MessageSquare className="mr-1 inline h-3 w-3" /> Waiting for output…
                </span>
              )}
              {!isComplete && output && <span className="animate-pulse">▍</span>}
            </div>

            {toolCalls.length > 0 && (
              <div>
                <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Tool calls
                </p>
                <ul className="flex flex-wrap gap-2">
                  {toolCalls.map((t) => (
                    <li
                      key={t.idx}
                      className="inline-flex items-center gap-1.5 rounded-full border bg-card px-2 py-1 text-xs"
                      title={t.args ? JSON.stringify(t.args) : undefined}
                    >
                      <Wrench className="h-3 w-3 text-muted-foreground" aria-hidden />
                      <span className="font-mono">{t.name}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          <div className="flex items-start justify-center">
            <ConfidenceGauge confidence={confidence ?? 0} size={110} />
          </div>
        </div>

        {stream.error && (
          <p className="mt-3 text-xs text-amber-600 dark:text-amber-400">
            Live stream unavailable: {stream.error}.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
