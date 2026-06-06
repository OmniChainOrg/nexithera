'use client';

import { Tooltip } from '@/components/ui/tooltip';
import { sortTornadoData, formatProbability } from '@/lib/utils/clinical-forecast';
import type { ForecastSensitivity } from '@/lib/api/forecast';
import { cn } from '@/lib/utils/cn';

interface TornadoPlotProps {
  sensitivity: ForecastSensitivity | null | undefined;
  baseProbability: number;
  /** Called with the factor name when a row is clicked. */
  onFactorClick?: (factor: string) => void;
  className?: string;
}

/**
 * Horizontal tornado plot showing sensitivity of the forecast to each
 * trial-design / evidence variable. Rows are sorted by |high − low|
 * descending. Click → notify parent (Scenario Explorer focuses the slider).
 */
export function TornadoPlot({
  sensitivity,
  baseProbability,
  onFactorClick,
  className,
}: TornadoPlotProps) {
  const rows = sortTornadoData(sensitivity?.tornado_data);

  if (rows.length === 0) {
    return (
      <div className={cn('text-sm text-muted-foreground', className)}>
        No sensitivity data available for this forecast.
      </div>
    );
  }

  // Compute the displayed probability range. Each row gives `low` and `high`
  // *probability* values (when low_probability/high_probability are present)
  // or falls back to the raw factor extremes.
  const points = rows.flatMap((r) => [
    r.low_probability ?? r.low ?? baseProbability,
    r.high_probability ?? r.high ?? baseProbability,
    baseProbability,
  ]);
  const min = Math.max(0, Math.min(...points, 0));
  const max = Math.min(1, Math.max(...points, 1));
  const span = Math.max(0.0001, max - min);
  const project = (v: number) => ((v - min) / span) * 100;

  return (
    <div
      className={cn('flex w-full flex-col gap-2', className)}
      data-testid="tornado-plot"
    >
      <div className="space-y-2">
        {rows.map((row) => {
          const low = row.low_probability ?? row.low ?? baseProbability;
          const high = row.high_probability ?? row.high ?? baseProbability;
          const leftPct = project(Math.min(low, baseProbability));
          const rightPct = project(Math.max(high, baseProbability));
          const widthPct = Math.max(2, rightPct - leftPct);
          const basePct = project(baseProbability);

          const interactive = !!onFactorClick;
          return (
            <button
              key={row.factor}
              type="button"
              onClick={interactive ? () => onFactorClick(row.factor) : undefined}
              disabled={!interactive}
              className={cn(
                'group grid w-full grid-cols-[minmax(0,12rem)_minmax(0,1fr)] items-center gap-3 rounded-md px-2 py-1 text-left text-xs',
                interactive && 'hover:bg-muted/60 focus:bg-muted/60 focus:outline-none',
              )}
              data-testid={`tornado-row-${row.factor}`}
              aria-label={`${row.factor}: low ${formatProbability(low)} → high ${formatProbability(high)}`}
            >
              <span className="truncate text-foreground">{row.factor}</span>
              <Tooltip
                content={
                  <span className="block text-xs">
                    <strong>{row.factor}</strong>
                    <br />
                    low {row.low} → {formatProbability(low)}
                    <br />
                    base → {formatProbability(baseProbability)}
                    <br />
                    high {row.high} → {formatProbability(high)}
                    <br />
                    Impact: ±{(row.impact ?? 0).toFixed(2)}
                  </span>
                }
              >
                <span className="relative block h-5 w-full overflow-hidden rounded-sm bg-muted/40">
                  {/* low half */}
                  <span
                    className="absolute top-0 h-full bg-red-500/70"
                    style={{
                      left: `${leftPct}%`,
                      width: `${Math.max(0, basePct - leftPct)}%`,
                    }}
                  />
                  {/* high half */}
                  <span
                    className="absolute top-0 h-full bg-emerald-500/70"
                    style={{
                      left: `${basePct}%`,
                      width: `${Math.max(0, rightPct - basePct)}%`,
                    }}
                  />
                  {/* base line */}
                  <span
                    className="absolute top-0 h-full w-px bg-foreground"
                    style={{ left: `${basePct}%` }}
                    aria-hidden
                  />
                  {/* Min width safety so single-point bars are visible */}
                  <span className="sr-only">width {widthPct.toFixed(0)}%</span>
                </span>
              </Tooltip>
            </button>
          );
        })}
      </div>
      <div className="flex items-center justify-between text-[0.7rem] text-muted-foreground">
        <span>{formatProbability(min)}</span>
        <span>Base probability: {formatProbability(baseProbability)}</span>
        <span>{formatProbability(max)}</span>
      </div>
    </div>
  );
}
