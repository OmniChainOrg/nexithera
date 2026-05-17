'use client';

import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
} from 'recharts';
import type { Scorecard } from '@/lib/types/genovate';

export function ScorecardRadar({ scorecard }: { scorecard: Scorecard }) {
  const data = [
    { dim: 'Evidence', value: scorecard.evidence_score },
    { dim: 'Simulation', value: scorecard.simulation_score },
    { dim: 'Safety', value: scorecard.safety_score },
    { dim: 'Formulation', value: scorecard.formulation_score },
    { dim: 'Translational', value: scorecard.translational_score },
    { dim: 'Program fit', value: scorecard.program_fit_score },
  ];

  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data} outerRadius="75%">
          <PolarGrid stroke="hsl(var(--border))" />
          <PolarAngleAxis dataKey="dim" tick={{ fontSize: 11 }} />
          <PolarRadiusAxis angle={30} domain={[0, 1]} tick={{ fontSize: 10 }} />
          <Radar
            name="Score"
            dataKey="value"
            stroke="hsl(var(--primary))"
            fill="hsl(var(--primary))"
            fillOpacity={0.35}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
