import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest';
import { WebSocketClient } from '@/lib/websocket/client';

/**
 * MockWebSocket simulates just enough of the browser `WebSocket` API for the
 * client's lifecycle / pooling logic.
 */
class MockWebSocket {
  static instances: MockWebSocket[] = [];
  static OPEN = 1;
  static CLOSED = 3;
  readonly url: string;
  onopen: (() => void) | null = null;
  onmessage: ((ev: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;
  closed = false;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  triggerOpen() {
    this.onopen?.();
  }
  triggerMessage(data: unknown) {
    this.onmessage?.({ data: typeof data === 'string' ? data : JSON.stringify(data) });
  }
  triggerClose() {
    this.closed = true;
    this.onclose?.();
  }

  close() {
    this.triggerClose();
  }
}

beforeEach(() => {
  MockWebSocket.instances = [];
  // @ts-ignore stubbing for tests
  globalThis.window = globalThis.window ?? {};
  // @ts-expect-error stubbing for tests
  globalThis.window.WebSocket = MockWebSocket;
  // @ts-expect-error stubbing for tests
  globalThis.WebSocket = MockWebSocket;
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('WebSocketClient', () => {
  it('pools connections per topic and tears down on last unsubscribe', () => {
    const client = new WebSocketClient({ baseUrl: 'ws://test/ws' });

    const messagesA: unknown[] = [];
    const messagesB: unknown[] = [];

    const unsubA = client.subscribe('cxu', 'x1', (m) => messagesA.push(m));
    const unsubB = client.subscribe('cxu', 'x1', (m) => messagesB.push(m));

    // Pool: one underlying socket only.
    expect(MockWebSocket.instances).toHaveLength(1);
    const sock = MockWebSocket.instances[0];
    expect(sock.url).toBe('ws://test/ws/cxu/x1');

    sock.triggerOpen();
    sock.triggerMessage({ iteration: 1 });
    expect(messagesA).toEqual([{ iteration: 1 }]);
    expect(messagesB).toEqual([{ iteration: 1 }]);

    unsubA();
    // Socket still open because B is subscribed.
    expect(sock.closed).toBe(false);

    unsubB();
    expect(sock.closed).toBe(true);
  });

  it('reconnects with exponential backoff on close', () => {
    const client = new WebSocketClient({
      baseUrl: 'ws://test/ws',
      initialBackoffMs: 100,
      maxBackoffMs: 5_000,
    });

    const statuses: string[] = [];
    client.subscribe('agent', 'run-1', () => undefined, (s) => statuses.push(s));

    const first = MockWebSocket.instances[0];
    first.triggerOpen();
    first.triggerClose();

    // Reconnect timer is pending; advance enough time to trigger it.
    vi.advanceTimersByTime(5_000);
    expect(MockWebSocket.instances.length).toBeGreaterThanOrEqual(2);
    expect(statuses).toContain('open');
    expect(statuses).toContain('reconnecting');
  });

  it('gives up after maxRetries reconnects', () => {
    const client = new WebSocketClient({
      baseUrl: 'ws://test/ws',
      initialBackoffMs: 1,
      maxBackoffMs: 2,
      maxRetries: 2,
    });
    const statuses: string[] = [];
    client.subscribe('program', 'p1', () => undefined, (s, e) => {
      statuses.push(s + (e ? `:${e}` : ''));
    });

    for (let i = 0; i < 5; i++) {
      const last = MockWebSocket.instances[MockWebSocket.instances.length - 1];
      last.triggerClose();
      vi.advanceTimersByTime(50);
    }
    expect(statuses.some((s) => s.startsWith('error'))).toBe(true);
  });
});
