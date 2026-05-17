'use client';

import { useEffect } from 'react';
import { Toaster } from 'react-hot-toast';
import { useWebSocketStore } from '@/lib/stores/websocket-store';

/**
 * Mounts the `react-hot-toast` portal once for the whole dashboard and
 * (optionally) requests permission for desktop notifications when the user
 * opts in via the settings page.
 *
 * The component renders no visible UI besides the toast region itself.
 */
export function NotificationToaster() {
  const desktopEnabled = useWebSocketStore((s) => s.desktopNotificationsEnabled);

  useEffect(() => {
    if (!desktopEnabled) return;
    if (typeof window === 'undefined' || !('Notification' in window)) return;
    if (Notification.permission === 'default') {
      // Async — ignore the return value (browser may decline silently).
      Notification.requestPermission().catch(() => undefined);
    }
  }, [desktopEnabled]);

  return (
    <Toaster
      position="top-right"
      toastOptions={{
        duration: 4000,
        className: 'text-sm',
      }}
    />
  );
}
