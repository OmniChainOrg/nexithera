import { beforeEach, describe, expect, it, vi } from 'vitest';
import { targetDiscoveryApi } from '@/lib/api/target-discovery';

beforeEach(() => vi.unstubAllGlobals());

describe('targetDiscoveryApi', () => {
  it('posts to discover targets endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ run_id: 'run1', program_id: 'p1', targets: [], generated_at: 'now' }) });
    vi.stubGlobal('fetch', fetchMock);
    await targetDiscoveryApi.discover({ program_id: 'p1', max_results: 10 });
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/agents/discover-targets'), expect.objectContaining({ method: 'POST', body: JSON.stringify({ program_id: 'p1', max_results: 10 }) }));
  });
});
