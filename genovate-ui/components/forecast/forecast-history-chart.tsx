'use client';

import {
  Area,
  ComposedChart,
  Line,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { EmptyState } from '@/components/common/empty-state';
import type { ForecastHistoryEvent } from '@/lib/api/forecast';

interface ForecastHistoryChartProps {
  events: ForecastHistoryEvent[] | null | undefined;
  loading?: boolean;
}

export function ForecastHistoryChart({ events, loading }: ForecastHistoryChartProps) {
  if (!events || events.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Forecast history</CardTitle>
        </CardHeader>
        <CardContent>
          <EmptyState
            title={loading ? 'Loading…' : 'No history yet'}
            description="History will appear here as the forecast is recalculated."
          />
        </CardContent>
      </Card>
    );
  }

  const data = events
    .slice()
    .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
    .map((e) => ({
      timestamp: e.timestamp,
      probability: e.probability,
      ci_lo: e.confidence_interval?.[0] ?? e.probability,
      ci_hi: e.confidence_interval?.[1] ?? e.probability,
      ribbon: [
        e.confidence_interval?.[0] ?? e.probability,
        e.confidence_interval?.[1] ?? e.probability,
      ] as [number, number],
      trigger: e.trigger ?? '',
      description: e.description ?? '',
    }));

  return (
    <Card>
      <CardHeader>
        <CardTitle>Forecast history</CardTitle>
      </CardHeader>
      <CardContent className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 10, right: 16, bottom: 10, left: 0 }}>
            <XAxis
              dataKey="timestamp"
              tickFormatter={(v: string) => new Date(v).toLocaleDateString()}
              fontSize={11}
            />
            <YAxis domain={[0, 1]} tickFormatter={(v: number) => `${Math.round(v * 100)}%`} fontSize={11} />
            <RechartsTooltip
              formatter={(value: unknown, name: unknown) => [
                typeof value === 'number' ? `${(value * 100).toFixed(1)}%` : String(value),
                String(name),
              ]}
              labelFormatter={(label) => new Date(String(label)).toLocaleString()}
            />
            <Area
              type="monotone"
              dataKey="ribbon"
              stroke="none"
              fill="#10b981"
              fillOpacity={0.15}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="probability"
              stroke="#10b981"
              strokeWidth={2}
              dot={{ r: 3 }}
              activeDot={{ r: 5 }}
            />
            {data.map(
              (d) =>
                d.trigger && (
                  <ReferenceDot
                    key={`${d.timestamp}-${d.trigger}`}
                    x={d.timestamp}
                    y={d.probability}
                    r={4}
                    fill="#3b82f6"
                    stroke="none"
                  />
                ),
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
