import * as React from 'react';
import { cn } from '@/lib/utils/cn';

export interface ProgressProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Value 0–100. */
  value: number;
  /** Color of the filled bar (tailwind class). */
  indicatorClassName?: string;
}

/**
 * Minimal progress bar. We avoid `@radix-ui/react-progress` to keep the
 * dependency footprint small — Tailwind handles the visuals and we expose
 * the same `value` (0–100) contract.
 */
export const Progress = React.forwardRef<HTMLDivElement, ProgressProps>(
  ({ className, value, indicatorClassName, ...props }, ref) => {
    const clamped = Math.max(0, Math.min(100, value));
    return (
      <div
        ref={ref}
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={clamped}
        className={cn(
          'relative h-2 w-full overflow-hidden rounded-full bg-secondary',
          className,
        )}
        {...props}
      >
        <div
          className={cn(
            'h-full rounded-full bg-primary transition-all',
            indicatorClassName,
          )}
          style={{ width: `${clamped}%` }}
        />
      </div>
    );
  },
);
Progress.displayName = 'Progress';
