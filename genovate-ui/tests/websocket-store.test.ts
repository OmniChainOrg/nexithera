import { describe, expect, it, beforeEach } from 'vitest';
import {
  selectGlobalStatus,
  useWebSocketStore,
} from '@/lib/stores/websocket-store';

beforeEach(() => {
  useWebSocketStore.setState({ streams: {}, notifications: [] });
});

describe('useWebSocketStore', () => {
  it('records and removes stream status', () => {
    useWebSocketStore.getState().setStreamStatus('cxu', 'abc', 'open');
    expect(useWebSocketStore.getState().streams['cxu:abc']).toBe('open');

    useWebSocketStore.getState().removeStream('cxu', 'abc');
    expect(useWebSocketStore.getState().streams['cxu:abc']).toBeUndefined();
  });

  it('caps notifications and assigns ids', () => {
    const { pushNotification } = useWebSocketStore.getState();
    for (let i = 0; i < 60; i++) {
      pushNotification({ title: `n${i}`, level: 'info' });
    }
    const list = useWebSocketStore.getState().notifications;
    expect(list.length).toBe(50);
    // newest first
    expect(list[0].title).toBe('n59');
    expect(list[0].id).toBeTruthy();
  });

  it('selectGlobalStatus returns worst-case status', () => {
    const { setStreamStatus } = useWebSocketStore.getState();
    setStreamStatus('cxu', 'a', 'open');
    setStreamStatus('agent', 'b', 'reconnecting');
    setStreamStatus('program', 'p', 'open');
    expect(selectGlobalStatus(useWebSocketStore.getState())).toBe('reconnecting');

    setStreamStatus('agent', 'b', 'error');
    expect(selectGlobalStatus(useWebSocketStore.getState())).toBe('error');
  });

  it('selectGlobalStatus is idle when no streams', () => {
    expect(selectGlobalStatus(useWebSocketStore.getState())).toBe('idle');
  });
});
