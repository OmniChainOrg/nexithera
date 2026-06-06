'use client';

import { Tooltip } from '@/components/ui/tooltip';
import {
  DECOMPOSITION_UNCERTAINTY_COLOR,
  buildDecompositionSegments,
  formatProbability,
} from '@/lib/utils/clinical-forecast';
import type { ForecastDecomposition } from '@/lib/api/forecast';
import { cn } from '@/lib/utils/cn';

interface DecompositionBarsProps {
  decomposition: ForecastDecomposition | null | undefined;
  probability: number;
  /** Optional per-factor rationales surfaced in tooltips. */
  rationales?: Record<string, string | null | undefined> | null;
  className?: string;
}

/**
 * Horizontal stacked bar showing how individual agents contribute to the
 * final probability. Anchors the stacked bar to 1.0 so the "Other /
 * uncertainty" segment is always visible.
 */
export function DecompositionBars({
  decomposition,
  probability,
  rationales,
  className,
}: DecompositionBarsProps) {
  const { segments, uncertaintyContribution } = buildDecompositionSegments(
    decomposition,
    probability,
  );

  if (segments.length === 0 && uncertaintyContribution >= 1) {
    return (
      <div className={cn('text-sm text-muted-foreground', className)}>
        No decomposition data available for this forecast.
      </div>
    );
  }

  return (
    <div
      className={cn('flex w-full flex-col gap-3', className)}
      data-testid="decomposition-bars"
    >
      <div
        className="flex h-8 w-full overflow-hidden rounded-md bg-muted/30"
        role="img"
        aria-label="Forecast decomposition"
      >
        {segments.map((seg) => (
          <Tooltip
            key={seg.key}
            content={
              <span className="block text-xs">
                <strong>{seg.label}</strong>: {formatProbability(seg.contribution, 1)}
                {rationales?.[seg.key] ? (
                  <>
                    <br />
                    {rationales[seg.key]}
                  </>
                ) : null}
              </span>
            }
          >
            <span
              data-testid={`decomposition-segment-${seg.key}`}
              className="block h-full transition-all"
              style={{
                width: `${seg.contribution * 100}%`,
                backgroundColor: seg.color,
              }}
              aria-label={`${seg.label} ${formatProbability(seg.contribution, 1)}`}
            />
          </Tooltip>
        ))}
        {uncertaintyContribution > 0 && (
          <Tooltip content="Other factors / unexplained uncertainty">
            <span
              data-testid="decomposition-segment-uncertainty"
              className="block h-full"
              style={{
                width: `${uncertaintyContribution * 100}%`,
                backgroundColor: DECOMPOSITION_UNCERTAINTY_COLOR,
              }}
              aria-label="Other / uncertainty"
            />
          </Tooltip>
        )}
      </div>

      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
        {segments.map((seg) => (
          <li key={seg.key} className="flex items-center gap-1.5">
            <span
              className="inline-block h-2.5 w-2.5 rounded-sm"
              style={{ backgroundColor: seg.color }}
              aria-hidden
            />
            <span>
              {seg.label} ({formatProbability(seg.contribution, 0)})
            </span>
          </li>
        ))}
        {uncertaintyContribution > 0 && (
          <li className="flex items-center gap-1.5">
            <span
              className="inline-block h-2.5 w-2.5 rounded-sm"
              style={{ backgroundColor: DECOMPOSITION_UNCERTAINTY_COLOR }}
              aria-hidden
            />
            <span>Other / uncertainty ({formatProbability(uncertaintyContribution, 0)})</span>
          </li>
        )}
      </ul>
    </div>
  );
}
