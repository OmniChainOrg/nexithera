/**
 * Singleton WebSocket client for the Genovate dashboard.
 *
 * Responsibilities:
 *  - Connection pooling: at most one underlying socket per (channel, id) topic;
 *    every subscriber on the same topic shares it.
 *  - Auto-reconnect with exponential backoff (jittered, capped).
 *  - Lifecycle / status events forwarded to subscribers so UI can render dots,
 *    toasts, and fall back to polling when permanently unavailable.
 *  - Browser-only: SSR-safe (no `window` access at import time).
 */

import type { ConnectionStatus, StreamChannel } from '@/lib/types/websocket';

export interface WSClientOptions {
  /** Base WS URL, e.g. `ws://localhost:8000/ws`. */
  baseUrl?: string;
  /** Initial backoff in ms. */
  initialBackoffMs?: number;
  /** Cap for the backoff in ms. */
  maxBackoffMs?: number;
  /** Maximum reconnect attempts before giving up (status='error'). */
  maxRetries?: number;
}

type Listener<T> = (msg: T) => void;
type StatusListener = (status: ConnectionStatus, error?: string) => void;

interface Topic {
  channel: StreamChannel;
  id: string;
  url: string;
  socket: WebSocket | null;
  status: ConnectionStatus;
  attempts: number;
  reconnectTimer: ReturnType<typeof setTimeout> | null;
  manualClose: boolean;
  messageListeners: Set<Listener<unknown>>;
  statusListeners: Set<StatusListener>;
}

const DEFAULTS: Required<Omit<WSClientOptions, 'baseUrl'>> & { baseUrl: string } = {
  baseUrl:
    (typeof process !== 'undefined' && process.env?.NEXT_PUBLIC_WS_URL) ||
    'ws://localhost:8000/ws',
  initialBackoffMs: 500,
  maxBackoffMs: 30_000,
  maxRetries: 10,
};

export class WebSocketClient {
  private readonly opts: Required<WSClientOptions> & { baseUrl: string };
  private readonly topics = new Map<string, Topic>();

  constructor(opts: WSClientOptions = {}) {
    this.opts = { ...DEFAULTS, ...opts } as Required<WSClientOptions> & { baseUrl: string };
  }

  /** Is the runtime able to open a WebSocket at all? */
  static isSupported(): boolean {
    return typeof window !== 'undefined' && typeof window.WebSocket !== 'undefined';
  }

  /**
   * Subscribe to a channel/id topic. Returns an unsubscribe function that, when
   * called, decrements the topic's refcount and tears down the underlying socket
   * once the last subscriber leaves.
   */
  subscribe<T>(
    channel: StreamChannel,
    id: string,
    onMessage: Listener<T>,
    onStatus?: StatusListener,
  ): () => void {
    if (!WebSocketClient.isSupported()) {
      onStatus?.('error', 'WebSocket not supported in this environment');
      return () => undefined;
    }

    const key = topicKey(channel, id);
    let topic = this.topics.get(key);
    if (!topic) {
      topic = {
        channel,
        id,
        url: this.buildUrl(channel, id),
        socket: null,
        status: 'idle',
        attempts: 0,
        reconnectTimer: null,
        manualClose: false,
        messageListeners: new Set(),
        statusListeners: new Set(),
      };
      this.topics.set(key, topic);
    }

    topic.messageListeners.add(onMessage as Listener<unknown>);
    if (onStatus) topic.statusListeners.add(onStatus);

    // Immediately surface current status to the new subscriber.
    onStatus?.(topic.status);

    if (!topic.socket) {
      this.openTopic(topic);
    }

    return () => {
      topic!.messageListeners.delete(onMessage as Listener<unknown>);
      if (onStatus) topic!.statusListeners.delete(onStatus);
      if (topic!.messageListeners.size === 0 && topic!.statusListeners.size === 0) {
        this.closeTopic(topic!);
        this.topics.delete(key);
      }
    };
  }

  /** Force-close every pooled connection (mostly useful for tests / HMR). */
  closeAll(): void {
    for (const topic of this.topics.values()) {
      this.closeTopic(topic);
    }
    this.topics.clear();
  }

  /** Current pooled status for a given topic, useful for fallback decisions. */
  statusFor(channel: StreamChannel, id: string): ConnectionStatus {
    return this.topics.get(topicKey(channel, id))?.status ?? 'idle';
  }

  // ── private ────────────────────────────────────────────────────────────────

  private buildUrl(channel: StreamChannel, id: string): string {
    const base = this.opts.baseUrl.replace(/\/$/, '');
    return `${base}/${channel}/${encodeURIComponent(id)}`;
  }

  private openTopic(topic: Topic): void {
    topic.manualClose = false;
    this.setStatus(topic, topic.attempts === 0 ? 'connecting' : 'reconnecting');

    let socket: WebSocket;
    try {
      socket = new WebSocket(topic.url);
    } catch (err) {
      this.setStatus(topic, 'error', err instanceof Error ? err.message : 'WebSocket failed to open');
      this.scheduleReconnect(topic);
      return;
    }
    topic.socket = socket;

    socket.onopen = () => {
      topic.attempts = 0;
      this.setStatus(topic, 'open');
    };

    socket.onmessage = (ev) => {
      let payload: unknown = ev.data;
      if (typeof ev.data === 'string') {
        try {
          payload = JSON.parse(ev.data);
        } catch {
          // Non-JSON frames are surfaced as-is.
        }
      }
      for (const listener of topic.messageListeners) {
        try {
          listener(payload);
        } catch (err) {
          // eslint-disable-next-line no-console
          console.error('[ws] listener threw for', topic.url, err);
        }
      }
    };

    socket.onerror = () => {
      // The browser does not expose details; rely on onclose for reconnects.
      this.setStatus(topic, 'error', 'WebSocket error');
    };

    socket.onclose = () => {
      topic.socket = null;
      if (topic.manualClose) {
        this.setStatus(topic, 'closed');
        return;
      }
      this.scheduleReconnect(topic);
    };
  }

  private scheduleReconnect(topic: Topic): void {
    if (topic.manualClose) return;
    if (topic.attempts >= this.opts.maxRetries) {
      this.setStatus(topic, 'error', 'Max reconnect attempts reached');
      return;
    }
    const attempt = topic.attempts++;
    const expo = Math.min(this.opts.maxBackoffMs, this.opts.initialBackoffMs * 2 ** attempt);
    const jitter = Math.random() * 0.3 * expo;
    const delay = Math.round(expo + jitter);
    this.setStatus(topic, 'reconnecting');
    topic.reconnectTimer = setTimeout(() => {
      topic.reconnectTimer = null;
      // Topic may have been torn down while waiting.
      if (this.topics.get(topicKey(topic.channel, topic.id)) === topic) {
        this.openTopic(topic);
      }
    }, delay);
  }

  private closeTopic(topic: Topic): void {
    topic.manualClose = true;
    if (topic.reconnectTimer) {
      clearTimeout(topic.reconnectTimer);
      topic.reconnectTimer = null;
    }
    if (topic.socket) {
      try {
        topic.socket.close();
      } catch {
        // ignore
      }
      topic.socket = null;
    }
    topic.messageListeners.clear();
    topic.statusListeners.clear();
    topic.status = 'closed';
  }

  private setStatus(topic: Topic, status: ConnectionStatus, error?: string): void {
    topic.status = status;
    for (const listener of topic.statusListeners) {
      try {
        listener(status, error);
      } catch (err) {
        // eslint-disable-next-line no-console
        console.error('[ws] status listener threw', err);
      }
    }
  }
}

function topicKey(channel: StreamChannel, id: string): string {
  return `${channel}:${id}`;
}

let singleton: WebSocketClient | null = null;

/** Process-wide singleton (lazy so SSR import is safe). */
export function getWebSocketClient(): WebSocketClient {
  if (!singleton) {
    singleton = new WebSocketClient();
  }
  return singleton;
}

/** Test seam — replace the singleton (e.g., for unit tests). */
export function __setWebSocketClient(client: WebSocketClient | null): void {
  if (singleton) singleton.closeAll();
  singleton = client;
}
