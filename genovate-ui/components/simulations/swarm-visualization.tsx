'use client';

import { useMemo } from 'react';
import { confidenceColor } from '@/lib/utils/colors';

interface SwarmMember {
  id: string;
  consensus: number;
  label?: string;
}

interface SwarmVisualizationProps {
  members: SwarmMember[];
  consensus: number;
}

/**
 * Lightweight SVG swarm visualization — avoids depending on vis-network
 * at first paint while still illustrating consensus.
 */
export function SwarmVisualization({ members, consensus }: SwarmVisualizationProps) {
  const layout = useMemo(() => {
    const n = Math.max(members.length, 1);
    return members.map((m, i) => {
      const angle = (i / n) * Math.PI * 2;
      return { ...m, x: 150 + Math.cos(angle) * 100, y: 150 + Math.sin(angle) * 100 };
    });
  }, [members]);

  return (
    <div className="rounded-lg border p-3">
      <div className="mb-2 flex items-center justify-between text-sm">
        <span className="font-medium">Swarm consensus</span>
        <span className="font-mono" style={{ color: confidenceColor(consensus) }}>
          {(consensus * 100).toFixed(0)}%
        </span>
      </div>
      <svg viewBox="0 0 300 300" className="h-64 w-full">
        {layout.map((m) => (
          <line
            key={`l-${m.id}`}
            x1={150}
            y1={150}
            x2={m.x}
            y2={m.y}
            stroke="currentColor"
            className="text-muted-foreground/30"
            strokeWidth={0.5 + m.consensus * 2}
          />
        ))}
        <circle cx={150} cy={150} r={10} fill="hsl(var(--primary))" />
        {layout.map((m) => (
          <g key={m.id}>
            <circle cx={m.x} cy={m.y} r={6} fill={confidenceColor(m.consensus)} />
            {m.label && (
              <text x={m.x} y={m.y - 10} textAnchor="middle" className="fill-foreground text-[10px]">
                {m.label}
              </text>
            )}
          </g>
        ))}
      </svg>
    </div>
  );
}
