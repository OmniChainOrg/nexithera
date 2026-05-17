import { cn } from '@/lib/utils/cn';
import { confidenceTier, confidenceColor } from '@/lib/utils/colors';
import { formatPercent } from '@/lib/utils/formatters';

interface ConfidenceBadgeProps {
  confidence: number;
  className?: string;
}

/**
 * Inline badge showing a confidence value with semantic color.
 * Used by agent runs, hypothesis cards, and review summaries.
 */
export function ConfidenceBadge({ confidence, className }: ConfidenceBadgeProps) {
  const tier = confidenceTier(confidence);
  const color = confidenceColor(confidence);

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium',
        className,
      )}
      style={{ color, backgroundColor: `${color}1a` }}
      aria-label={`Confidence ${tier}: ${formatPercent(confidence)}`}
      data-confidence-tier={tier}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: color }} />
      {formatPercent(confidence)}
    </span>
  );
}
