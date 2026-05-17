import { confidenceColor, confidenceTier } from '@/lib/utils/colors';
import { formatPercent } from '@/lib/utils/formatters';

interface ConfidenceGaugeProps {
  confidence: number;
  size?: number;
}

/**
 * Circular SVG gauge for agent confidence (0..1).
 * Color follows the confidence tier (high/medium/low).
 */
export function ConfidenceGauge({ confidence, size = 120 }: ConfidenceGaugeProps) {
  const clamped = Math.max(0, Math.min(1, confidence));
  const color = confidenceColor(clamped);
  const tier = confidenceTier(clamped);
  const radius = (size - 12) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - clamped);

  return (
    <div className="inline-flex flex-col items-center" role="img" aria-label={`Confidence ${tier}`}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="currentColor"
          className="text-muted/40"
          strokeWidth={8}
          fill="none"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={color}
          strokeWidth={8}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
        <text
          x="50%"
          y="50%"
          textAnchor="middle"
          dy="0.35em"
          className="fill-foreground font-mono text-xl font-semibold"
        >
          {formatPercent(clamped)}
        </text>
      </svg>
      <span className="mt-1 text-xs uppercase tracking-wider text-muted-foreground">
        {tier} confidence
      </span>
    </div>
  );
}
