'use client';

import { useMemo } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { confidenceColor } from '@/lib/utils/colors';
import { useSwarmStream } from '@/lib/hooks/use-websocket';

interface SwarmProgressProps {
  swarmId: string;
  title?: string;
}

/**
 * Live swarm view fed by `/ws/swarm/{swarm_id}`.
 *
 *   ┌──────────────────────────┐
 *   │ Consensus over time      │  ← line chart of consensus_score
 *   ├──────────────────────────┤
 *   │ Member contributions     │  ← bar chart
 *   │ Diversity gauge          │  ← semicircle
 *   └──────────────────────────┘
 */
export function SwarmProgress({ swarmId, title = 'Swarm progress' }: SwarmProgressProps) {
  const stream = useSwarmStream(swarmId);
  const latest = stream.lastMessage;

  const consensusSeries = useMemo(
    () =>
      stream.messages.slice(-100).map((m, idx) => ({
        tick: idx + 1,
        consensus: Number((m.consensus_score * 100).toFixed(2)),
        diversity: Number((m.diversity_metric * 100).toFixed(2)),
      })),
    [stream.messages],
  );

  const members = latest?.member_results ?? [];

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-base">{title}</CardTitle>
          {latest && (
            <p className="text-xs text-muted-foreground">
              {latest.completed_members}/{latest.total_members} members
            </p>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="h-40 w-full rounded-md border bg-card">
          {consensusSeries.length === 0 ? (
            <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
              Waiting for swarm updates…
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={consensusSeries} margin={{ top: 8, right: 12, bottom: 4, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                <XAxis dataKey="tick" fontSize={10} />
                <YAxis domain={[0, 100]} fontSize={10} />
                <Tooltip formatter={(v: number) => `${v.toFixed(1)}%`} />
                <Line
                  type="monotone"
                  dataKey="consensus"
                  stroke="#16a34a"
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                  name="Consensus"
                />
                <Line
                  type="monotone"
                  dataKey="diversity"
                  stroke="#a855f7"
                  strokeWidth={1.5}
                  dot={false}
                  strokeDasharray="4 4"
                  isAnimationActive={false}
                  name="Diversity"
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <div className="md:col-span-2">
            <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Member contributions
            </p>
            <div className="h-36 w-full rounded-md border bg-card">
              {members.length === 0 ? (
                <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
                  No member data yet
                </div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={members} margin={{ top: 8, right: 12, bottom: 4, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                    <XAxis dataKey="cxu_id" fontSize={9} interval={0} angle={-25} dy={6} height={28} />
                    <YAxis fontSize={10} />
                    <Tooltip />
                    <Bar dataKey="contribution" isAnimationActive={false}>
                      {members.map((m) => (
                        <Cell key={m.cxu_id} fill={confidenceColor(m.contribution)} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>
          <div>
            <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Diversity
            </p>
            <DiversityGauge value={latest?.diversity_metric ?? 0} />
          </div>
        </div>

        {stream.error && (
          <p className="text-xs text-amber-600 dark:text-amber-400">
            Live stream unavailable: {stream.error}.
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function DiversityGauge({ value }: { value: number }) {
  const clamped = Math.max(0, Math.min(1, value));
  const angle = clamped * Math.PI;
  const r = 50;
  const cx = 60;
  const cy = 60;
  const x = cx + Math.cos(Math.PI - angle) * r;
  const y = cy - Math.sin(Math.PI - angle) * r;
  const color = confidenceColor(clamped);
  const arc = `M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${x} ${y}`;
  return (
    <div className="flex h-36 items-center justify-center rounded-md border bg-card">
      <svg viewBox="0 0 120 70" className="h-full">
        <path d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`} stroke="#e5e7eb" strokeWidth={8} fill="none" />
        <path d={arc} stroke={color} strokeWidth={8} fill="none" strokeLinecap="round" />
        <text x={cx} y={cy - 5} textAnchor="middle" fontSize="14" className="fill-foreground font-mono">
          {(clamped * 100).toFixed(0)}%
        </text>
      </svg>
    </div>
  );
}
