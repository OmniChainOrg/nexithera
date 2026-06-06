'use client';

/**
 * React hooks for the Genovate WebSocket streams.
 *
 *  - `useCXUStream(cxuId)`           → live CXU iteration messages
 *  - `useSwarmStream(swarmId)`       → live swarm consensus / member updates
 *  - `useAgentRunStream(runId)`      → streaming agent output chunks
 *  - `useProgramEvents(programId)`   → high-level program-wide events (kanban,
 *                                      reviews, evidence) and toasts
 *
 * Each hook also accepts an optional `enabled` flag and exposes the underlying
 * connection status so callers can render a fallback or display indicators.
 * When `WebSocket` is unsupported or repeatedly errors out, callers can safely
 * fall back to TanStack Query polling: the hooks never throw.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { getWebSocketClient } from '@/lib/websocket/client';
import { queryKeys } from './query-keys';
import {
  selectGlobalStatus,
  useWebSocketStore,
} from '@/lib/stores/websocket-store';
import type {
  AgentOutputMessage,
  ConnectionStatus,
  CXUIterationMessage,
  ProgramEventMessage,
  StreamChannel,
  SwarmUpdateMessage,
  WebSocketHookState,
} from '@/lib/types/websocket';

interface UseStreamOptions {
  enabled?: boolean;
}

function useStream<TMessage>(
  channel: StreamChannel,
  id: string | null | undefined,
  { enabled = true }: UseStreamOptions = {},
): WebSocketHookState<TMessage> & { messages: TMessage[]; reset: () => void } {
  const [status, setStatus] = useState<ConnectionStatus>('idle');
  const [error, setError] = useState<string | null>(null);
  const [lastMessage, setLastMessage] = useState<TMessage | null>(null);
  const [messages, setMessages] = useState<TMessage[]>([]);
  const hasEverConnectedRef = useRef(false);
  const [hasEverConnected, setHasEverConnected] = useState(false);

  const setStreamStatus = useWebSocketStore((s) => s.setStreamStatus);
  const removeStream = useWebSocketStore((s) => s.removeStream);

  const reset = useCallback(() => {
    setMessages([]);
    setLastMessage(null);
    setError(null);
  }, []);

  useEffect(() => {
    if (!enabled || !id) return;
    const client = getWebSocketClient();

    const unsubscribe = client.subscribe<TMessage>(
      channel,
      id,
      (msg) => {
        setLastMessage(msg);
        setMessages((prev) => {
          // Keep memory bounded — 500 messages is generous for streaming output.
          const next = prev.length >= 500 ? prev.slice(prev.length - 499) : prev.slice();
          next.push(msg);
          return next;
        });
      },
      (nextStatus, errMessage) => {
        setStatus(nextStatus);
        setStreamStatus(channel, id, nextStatus);
        if (nextStatus === 'open' && !hasEverConnectedRef.current) {
          hasEverConnectedRef.current = true;
          setHasEverConnected(true);
        }
        if (nextStatus === 'error') {
          setError(errMessage ?? 'WebSocket error');
        } else if (nextStatus === 'open') {
          setError(null);
        }
      },
    );

    return () => {
      unsubscribe();
      removeStream(channel, id);
    };
  }, [channel, id, enabled, setStreamStatus, removeStream]);

  return { status, lastMessage, error, hasEverConnected, messages, reset };
}

export function useCXUStream(cxuId: string | null | undefined, options?: UseStreamOptions) {
  return useStream<CXUIterationMessage>('cxu', cxuId, options);
}

export function useSwarmStream(swarmId: string | null | undefined, options?: UseStreamOptions) {
  return useStream<SwarmUpdateMessage>('swarm', swarmId, options);
}

export function useAgentRunStream(runId: string | null | undefined, options?: UseStreamOptions) {
  return useStream<AgentOutputMessage>('agent', runId, options);
}

export function useSimulationStream(
  runId: string | null | undefined,
  options?: UseStreamOptions,
) {
  return useStream<CXUIterationMessage | SwarmUpdateMessage>('simulation', runId, options);
}

/**
 * Subscribe to a program's high-level event channel. Side-effects:
 *  - Invalidates relevant TanStack Query caches so paginated lists refresh.
 *  - Pushes a toast and a notification entry into the Zustand store.
 *  - Optionally fires a desktop notification when the user has opted in and
 *    granted browser permission.
 */
export function useProgramEvents(
  programId: string | null | undefined,
  options?: UseStreamOptions,
) {
  const queryClient = useQueryClient();
  const pushNotification = useWebSocketStore((s) => s.pushNotification);
  const desktopEnabled = useWebSocketStore((s) => s.desktopNotificationsEnabled);

  const stream = useStream<ProgramEventMessage>('program', programId, options);
  const { lastMessage } = stream;

  useEffect(() => {
    if (!lastMessage || !programId) return;
    const message = lastMessage;
    const { title, body, level } = describeEvent(message);

    pushNotification({ title, body, level, programId });
    if (level === 'error') toast.error(title);
    else if (level === 'warning') toast(title, { icon: '⚠️' });
    else if (level === 'success') toast.success(title);
    else toast(title);

    if (desktopEnabled && typeof window !== 'undefined' && 'Notification' in window) {
      if (Notification.permission === 'granted') {
        try {
          // eslint-disable-next-line no-new
          new Notification(title, { body });
        } catch {
          // Some browsers throw for service-worker-only notifications.
        }
      }
    }

    const payload = message.payload ?? {};
    const payloadEntityId = typeof payload.entity_id === 'string' ? payload.entity_id : undefined;

    // Cache invalidation by event type.
    switch (message.event_type) {
      case 'candidate_created':
      case 'candidate_status_changed':
        queryClient.invalidateQueries({ queryKey: queryKeys.candidates.forProgram(programId) });
        break;
      case 'review_created':
        queryClient.invalidateQueries({
          queryKey: queryKeys.guardian.reviews({ program_id: programId }),
        });
        break;
      case 'agent_run_completed':
        queryClient.invalidateQueries({
          queryKey: queryKeys.agents.runs({ program_id: programId }),
        });
        break;
      case 'evidence_edge_added':
        queryClient.invalidateQueries({ queryKey: queryKeys.evidence.graph(programId) });
        break;
      case 'target_discovery.new':
        queryClient.invalidateQueries({ queryKey: queryKeys.targets.discover(programId) });
        break;
      case 'gap_analysis.completed':
        queryClient.invalidateQueries({ queryKey: queryKeys.analysis.gaps(programId) });
        break;
      case 'experiment.status_changed':
      case 'experiment.completed':
        queryClient.invalidateQueries({ queryKey: queryKeys.analysis.experiments(programId) });
        if (payloadEntityId) {
          queryClient.invalidateQueries({ queryKey: queryKeys.analysis.beliefTimeline(payloadEntityId) });
        }
        break;
      case 'guardian.bulk_complete':
        queryClient.invalidateQueries({
          queryKey: queryKeys.guardian.reviews({ program_id: programId }),
        });
        queryClient.invalidateQueries({ queryKey: queryKeys.candidates.forProgram(programId) });
        break;
      case 'forecast.updated':
        // payload may contain { candidate_id } — invalidate that candidate's
        // forecast cache, otherwise wildcard-invalidate clinical forecasts.
        {
          const candidateId =
            (lastMessage.payload?.candidate_id as string | undefined) ?? lastMessage.entity_id;
          if (candidateId) {
            queryClient.invalidateQueries({
              queryKey: queryKeys.forecast.clinical(candidateId),
              exact: false,
            });
            queryClient.invalidateQueries({
              queryKey: queryKeys.forecast.history(candidateId),
            });
          } else {
            queryClient.invalidateQueries({ queryKey: ['forecast'] });
          }
        }
        break;
    }
  }, [lastMessage, programId, desktopEnabled, pushNotification, queryClient]);

  return stream;
}

/**
 * Returns true when at least one open WS stream exists. Components can use
 * this to decide whether TanStack Query should poll as a fallback.
 */
export function useIsWebSocketHealthy(): boolean {
  const status = useWebSocketStore(selectGlobalStatus);
  return status === 'open' || status === 'connecting';
}

function describeEvent(msg: ProgramEventMessage): {
  title: string;
  body?: string;
  level: 'info' | 'success' | 'warning' | 'error';
} {
  switch (msg.event_type) {
    case 'candidate_created':
      return {
        title: 'New candidate created',
        body: msg.entity_id,
        level: 'success',
      };
    case 'candidate_status_changed':
      return {
        title: 'Candidate status changed',
        body:
          msg.old_status && msg.new_status
            ? `${msg.old_status} → ${msg.new_status}`
            : msg.entity_id,
        level: 'info',
      };
    case 'review_created':
      return { title: 'New Guardian review', body: msg.entity_id, level: 'warning' };
    case 'agent_run_completed':
      return { title: 'Agent run completed', body: msg.entity_id, level: 'success' };
    case 'evidence_edge_added':
      return { title: 'New evidence added', body: msg.entity_id, level: 'info' };
    case 'target_discovery.new':
      return { title: 'New target discovered', body: msg.entity_id, level: 'success' };
    case 'gap_analysis.completed':
      return { title: 'Gap analysis completed', body: msg.entity_id, level: 'success' };
    case 'experiment.status_changed':
      return { title: 'Experiment status changed', body: msg.new_status ?? msg.entity_id, level: 'info' };
    case 'experiment.completed':
      return { title: 'Experiment completed', body: msg.entity_id, level: 'success' };
    case 'guardian.bulk_complete':
      return { title: 'Bulk Guardian action complete', body: msg.entity_id, level: 'success' };
    case 'forecast.updated': {
      const prev = msg.payload?.previous_probability as number | undefined;
      const next = msg.payload?.new_probability as number | undefined;
      const trigger = (msg.payload?.trigger as string | undefined) ?? 'recalculation';
      const fmt = (v?: number) =>
        typeof v === 'number' ? `${Math.round(v * 100)}%` : '—';
      return {
        title: 'Forecast updated',
        body: `${fmt(prev)} → ${fmt(next)} (${trigger})`,
        level: 'info',
      };
    }
    default:
      return { title: 'Update received', body: msg.entity_id, level: 'info' };
  }
}
