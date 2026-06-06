'use client';

import { Area, CartesianGrid, Line, LineChart, ReferenceDot, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { BeliefTimeline as BeliefTimelineType } from '@/lib/types/genovate';

export function BeliefTimeline({ timeline }: { timeline?: BeliefTimelineType | null }) {
  const points = timeline?.points ?? [];
  if (!points.length) return <Card><CardContent className="p-6 text-center text-sm text-muted-foreground">No belief timeline data.</CardContent></Card>;
  const data = points.map((p) => ({ ...p, label: new Date(p.timestamp).toLocaleDateString(), range: [p.uncertainty_low ?? p.confidence, p.uncertainty_high ?? p.confidence] }));
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">Belief timeline</CardTitle></CardHeader>
      <CardContent className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 10, right: 20, bottom: 10, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="label" />
            <YAxis domain={[0, 1]} />
            <Tooltip />
            <Area dataKey="range" stroke="none" fill="#93c5fd" fillOpacity={0.25} />
            <Line type="monotone" dataKey="confidence" stroke="#2563eb" strokeWidth={2} />
            {data.filter((p) => p.experiment_id).map((p, i) => <ReferenceDot key={`${p.experiment_id}-${i}`} x={p.label} y={p.confidence} r={5} fill="#f59e0b" stroke="none" />)}
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
