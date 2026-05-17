import { create } from 'zustand';
import type {
  ConnectionStatus,
  NotificationEntry,
  StreamChannel,
} from '@/lib/types/websocket';

/**
 * Global WebSocket state used by the status indicator and toast system.
 *
 *  - `streams`   : per-topic ConnectionStatus, indexed by `${channel}:${id}`.
 *  - `notifications`: ring buffer of recent events for the bell / toast list.
 *  - Status of the *overall* dashboard is the worst-of: error > reconnecting >
 *    connecting > open > idle/closed.
 */

const MAX_NOTIFICATIONS = 50;

const STATUS_RANK: Record<ConnectionStatus, number> = {
  open: 0,
  idle: 1,
  closed: 1,
  connecting: 2,
  reconnecting: 3,
  error: 4,
};

interface WebSocketStoreState {
  streams: Record<string, ConnectionStatus>;
  notifications: NotificationEntry[];
  desktopNotificationsEnabled: boolean;

  setStreamStatus: (channel: StreamChannel, id: string, status: ConnectionStatus) => void;
  removeStream: (channel: StreamChannel, id: string) => void;

  pushNotification: (entry: Omit<NotificationEntry, 'id' | 'createdAt'>) => NotificationEntry;
  dismissNotification: (id: string) => void;
  clearNotifications: () => void;

  setDesktopNotificationsEnabled: (enabled: boolean) => void;
}

function streamKey(channel: StreamChannel, id: string): string {
  return `${channel}:${id}`;
}

export const useWebSocketStore = create<WebSocketStoreState>((set) => ({
  streams: {},
  notifications: [],
  desktopNotificationsEnabled: false,

  setStreamStatus: (channel, id, status) =>
    set((state) => ({ streams: { ...state.streams, [streamKey(channel, id)]: status } })),

  removeStream: (channel, id) =>
    set((state) => {
      const next = { ...state.streams };
      delete next[streamKey(channel, id)];
      return { streams: next };
    }),

  pushNotification: (entry) => {
    const full: NotificationEntry = {
      ...entry,
      id:
        typeof crypto !== 'undefined' && 'randomUUID' in crypto
          ? crypto.randomUUID()
          : `n_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      createdAt: Date.now(),
    };
    set((state) => ({
      notifications: [full, ...state.notifications].slice(0, MAX_NOTIFICATIONS),
    }));
    return full;
  },

  dismissNotification: (id) =>
    set((state) => ({ notifications: state.notifications.filter((n) => n.id !== id) })),

  clearNotifications: () => set({ notifications: [] }),

  setDesktopNotificationsEnabled: (enabled) => set({ desktopNotificationsEnabled: enabled }),
}));

/** Derive a single status for the header indicator. */
export function selectGlobalStatus(state: WebSocketStoreState): ConnectionStatus {
  const values = Object.values(state.streams);
  if (values.length === 0) return 'idle';
  return values.reduce<ConnectionStatus>((worst, current) => {
    return STATUS_RANK[current] > STATUS_RANK[worst] ? current : worst;
  }, 'open');
}
