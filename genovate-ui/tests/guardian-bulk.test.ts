import { beforeEach, describe, expect, it, vi } from 'vitest';
import { guardianApi } from '@/lib/api/guardian';

beforeEach(() => vi.unstubAllGlobals());

describe('guardianApi.bulk', () => {
  it('posts action and ids', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ approved_count: 2, killed_count: 0, parked_count: 0, failed_ids: [] }) });
    vi.stubGlobal('fetch', fetchMock);
    await guardianApi.bulk({ action: 'approve', review_ids: ['r1', 'r2'] });
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/guardian/bulk'), expect.objectContaining({ method: 'POST', body: JSON.stringify({ action: 'approve', review_ids: ['r1', 'r2'] }) }));
  });
});
