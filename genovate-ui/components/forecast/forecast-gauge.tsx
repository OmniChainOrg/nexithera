'use client';

import { useEffect, useState } from 'react';
import { Tooltip } from '@/components/ui/tooltip';
import {
  clampProbability,
  formatConfidenceInterval,
  formatProbability,
  gaugeColor,
} from '@/lib/utils/clinical-forecast';
import { cn } from '@/lib/utils/cn';

interface ForecastGaugeProps {
  probability: number;
  confidenceInterval?: [number | null | undefined, number | null | undefined] | null;
  label?: string;
  loading?: boolean;
  /** Diameter in px (desktop). Mobile auto-scales via CSS. */
  size?: number;
  className?: string;
}

const STROKE_WIDTH = 16;
const ARC_FRACTION = 0.75; // 270° arc — feels more "gauge-like".
const ANIMATION_MS = 1000;

/**
 * Animated circular forecast gauge with confidence-interval ribbon.
 *
 *   1. background arc (track)
 *   2. CI ribbon (lighter, wider)
 *   3. point-estimate arc (filled to target probability)
 *
 * On mount the point estimate fills from 0 → target over 1s ease-out;
 * subsequent prop changes ease to the new value.
 */
export function ForecastGauge({
  probability,
  confidenceInterval,
  label = 'P(meet primary endpoint)',
  loading = false,
  size = 200,
  className,
}: ForecastGaugeProps) {
  const target = clampProbability(probability);
  const [displayed, setDisplayed] = useState(0);

  useEffect(() => {
    let raf = 0;
    const start = performance.now();
    const initial = displayed;
    const delta = target - initial;

    function tick(now: number) {
      const t = Math.min(1, (now - start) / ANIMATION_MS);
      const eased = 1 - Math.pow(1 - t, 3); // ease-out cubic
      setDisplayed(initial + delta * eased);
      if (t < 1) raf = requestAnimationFrame(tick);
    }
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target]);

  const color = gaugeColor(displayed);
  const ciText = formatConfidenceInterval(confidenceInterval);

  const radius = size / 2 - STROKE_WIDTH;
  const circumference = 2 * Math.PI * radius;
  const arcLength = circumference * ARC_FRACTION;

  const ciLo = confidenceInterval?.[0] ?? null;
  const ciHi = confidenceInterval?.[1] ?? null;
  const ribbonFrom = ciLo != null ? clampProbability(ciLo) * arcLength : null;
  const ribbonTo = ciHi != null ? clampProbability(ciHi) * arcLength : null;

  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-2',
        loading && 'opacity-60',
        className,
      )}
      data-testid="forecast-gauge"
    >
      <div className="relative" style={{ width: size, height: size }}>
        <svg
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
          className="-rotate-[135deg]"
          role="img"
          aria-label={`Forecast probability ${formatProbability(target)}`}
        >
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="currentColor"
            strokeOpacity={0.1}
            strokeWidth={STROKE_WIDTH}
            strokeDasharray={`${arcLength} ${circumference}`}
            strokeLinecap="round"
            className="text-muted-foreground"
          />

          {ribbonFrom != null && ribbonTo != null && (
            <circle
              cx={size / 2}
              cy={size / 2}
              r={radius}
              fill="none"
              stroke={color.stroke}
              strokeOpacity={0.25}
              strokeWidth={STROKE_WIDTH + 6}
              strokeDasharray={`${Math.max(0, ribbonTo - ribbonFrom)} ${circumference}`}
              strokeDashoffset={-ribbonFrom}
              strokeLinecap="round"
              data-testid="forecast-gauge-ci-ribbon"
            />
          )}

          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={color.stroke}
            strokeWidth={STROKE_WIDTH}
            strokeDasharray={`${displayed * arcLength} ${circumference}`}
            strokeLinecap="round"
            style={{ transition: 'stroke 300ms ease-out' }}
            data-testid="forecast-gauge-arc"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
          <span
            className={cn('text-4xl font-bold tabular-nums', color.textClass)}
            data-testid="forecast-gauge-value"
          >
            {formatProbability(displayed)}
          </span>
          <span className="px-4 text-xs text-muted-foreground">{label}</span>
        </div>
      </div>
      {ciText && (
        <Tooltip content="95% confidence interval based on model uncertainty + data sparsity">
          <p
            className="text-xs text-muted-foreground"
            data-testid="forecast-gauge-ci-text"
          >
            {ciText}
          </p>
        </Tooltip>
      )}
    </div>
  );
}
