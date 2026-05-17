import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface ProgramStoreState {
  currentProgramId: string | null;
  setCurrentProgramId: (id: string | null) => void;
}

/**
 * Persists the currently selected program across page navigations and reloads.
 * Used by the global program selector in the header.
 */
export const useProgramStore = create<ProgramStoreState>()(
  persist(
    (set) => ({
      currentProgramId: null,
      setCurrentProgramId: (id) => set({ currentProgramId: id }),
    }),
    { name: 'genovate-current-program' },
  ),
);
