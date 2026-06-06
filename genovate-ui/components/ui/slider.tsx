'use client';

import * as React from 'react';
import { cn } from '@/lib/utils/cn';

export interface SliderProps {
  value: number;
  min?: number;
  max?: number;
  step?: number;
  onValueChange?: (v: number) => void;
  className?: string;
  id?: string;
  'aria-label'?: string;
}

/**
 * Native `<input type=range>` styled with Tailwind — no extra Radix dep.
 */
export function Slider({
  value,
  min = 0,
  max = 100,
  step = 1,
  onValueChange,
  className,
  ...rest
}: SliderProps) {
  return (
    <input
      type="range"
      value={value}
      min={min}
      max={max}
      step={step}
      onChange={(e) => onValueChange?.(Number(e.target.value))}
      className={cn(
        'h-2 w-full cursor-pointer appearance-none rounded-full bg-secondary accent-primary',
        className,
      )}
      {...rest}
    />
  );
}
