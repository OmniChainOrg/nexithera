'use client';

import { useEffect, useState } from 'react';
import { cn } from '@/lib/utils/cn';
import { selectGlobalStatus, useWebSocketStore } from '@/lib/stores/websocket-store';
import type { ConnectionStatus } from '@/lib/types/websocket';

/**
 * Header dot indicator for the overall WebSocket health.
 *
 *  green  → at least one stream open, none degraded
 *  yellow → connecting / reconnecting
 *  red    → error
 *  gray   → no active streams
 */
export function WebSocketStatus({ className }: { className?: string }) {
  const status = useWebSocketStore(selectGlobalStatus);
  const streamCount = useWebSocketStore((s) => Object.keys(s.streams).length);
  // Avoid SSR/CSR hydration mismatch for the dynamic count tooltip.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const { color, label } = describe(status);
  const title = mounted ? `${label} · ${streamCount} stream${streamCount === 1 ? '' : 's'}` : label;

  return (
    <div
      className={cn('inline-flex items-center gap-2 text-xs text-muted-foreground', className)}
      title={title}
      aria-label={title}
      role="status"
    >
      <span
        className={cn(
          'inline-block h-2.5 w-2.5 rounded-full ring-2 ring-background',
          color,
          status === 'connecting' || status === 'reconnecting' ? 'animate-pulse' : null,
        )}
        aria-hidden
      />
      <span className="hidden sm:inline">{label}</span>
    </div>
  );
}

function describe(status: ConnectionStatus): { color: string; label: string } {
  switch (status) {
    case 'open':
      return { color: 'bg-emerald-500', label: 'Live' };
    case 'connecting':
      return { color: 'bg-amber-500', label: 'Connecting' };
    case 'reconnecting':
      return { color: 'bg-amber-500', label: 'Reconnecting' };
    case 'error':
      return { color: 'bg-red-500', label: 'Offline' };
    case 'idle':
    case 'closed':
    default:
      return { color: 'bg-muted-foreground/40', label: 'Idle' };
  }
}
