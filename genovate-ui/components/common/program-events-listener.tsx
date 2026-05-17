'use client';

import { useProgramStore } from '@/lib/stores/program-store';
import { useProgramEvents } from '@/lib/hooks/use-websocket';

/**
 * Mounts the `/ws/program/{program_id}` subscription for the currently
 * selected program. Renders nothing — side effects only (toasts, cache
 * invalidations) live inside `useProgramEvents`.
 */
export function ProgramEventsListener() {
  const programId = useProgramStore((s) => s.currentProgramId);
  useProgramEvents(programId, { enabled: !!programId });
  return null;
}
