import { create } from 'zustand';

interface UIStoreState {
  sidebarCollapsed: boolean;
  theme: 'light' | 'dark' | 'system';
  activeModal: string | null;
  modalPayload: unknown;

  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  setTheme: (t: UIStoreState['theme']) => void;
  openModal: (name: string, payload?: unknown) => void;
  closeModal: () => void;
}

export const useUIStore = create<UIStoreState>((set) => ({
  sidebarCollapsed: false,
  theme: 'system',
  activeModal: null,
  modalPayload: null,
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
  setTheme: (t) => set({ theme: t }),
  openModal: (name, payload) => set({ activeModal: name, modalPayload: payload ?? null }),
  closeModal: () => set({ activeModal: null, modalPayload: null }),
}));
