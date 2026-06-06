'use client';

import * as React from 'react';
import { cn } from '@/lib/utils/cn';

interface TooltipProps {
  content: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  side?: 'top' | 'bottom';
}

/**
 * Lightweight hover/focus tooltip. Avoids `@radix-ui/react-tooltip` to keep
 * dependencies trim — uses CSS group-hover positioning.
 */
export function Tooltip({ content, children, className, side = 'top' }: TooltipProps) {
  if (content == null || content === '') return <>{children}</>;
  return (
    <span className="group relative inline-flex">
      {children}
      <span
        role="tooltip"
        className={cn(
          'pointer-events-none absolute left-1/2 z-50 hidden -translate-x-1/2 whitespace-pre-line rounded-md border bg-popover px-2 py-1 text-xs text-popover-foreground shadow-md group-hover:block group-focus-within:block',
          side === 'top' ? 'bottom-full mb-1' : 'top-full mt-1',
          'max-w-xs',
          className,
        )}
      >
        {content}
      </span>
    </span>
  );
}
