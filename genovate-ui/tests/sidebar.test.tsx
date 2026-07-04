import React from 'react';
import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { Sidebar } from '@/components/layout/sidebar';
import { useProgramStore } from '@/lib/stores/program-store';
import { useUIStore } from '@/lib/stores/ui-store';

vi.mock('next/navigation', () => ({
  usePathname: () => '/programs',
}));

describe('Sidebar', () => {
  beforeEach(() => {
    useUIStore.setState({ sidebarCollapsed: false });
    useProgramStore.setState({ currentProgramId: null });
  });

  it('shows Programs in the primary navigation', () => {
    render(<Sidebar />);

    const link = screen.getByRole('link', { name: 'Programs' });
    expect(link).toHaveAttribute('href', '/programs');
  });
});
