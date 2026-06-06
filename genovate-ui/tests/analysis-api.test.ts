import { beforeEach, describe, expect, it, vi } from 'vitest';
import { analysisApi } from '@/lib/api/analysis';

function mockFetch(json: unknown) {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => json });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

beforeEach(() => vi.unstubAllGlobals());

describe('analysisApi', () => {
  it('posts gap analysis input', async () => {
    const fetchMock = mockFetch({ program_id: 'p1', gaps: [], targets: [], diseases: [], generated_at: 'now' });
    await analysisApi.gapAnalysis({ program_id: 'p1', min_severity: 0.7 });
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/analysis/gap-analysis'), expect.objectContaining({ method: 'POST', body: JSON.stringify({ program_id: 'p1', min_severity: 0.7 }) }));
  });

  it('posts next experiments input', async () => {
    const fetchMock = mockFetch([]);
    await analysisApi.nextExperiments({ program_id: 'p1', limit: 5 });
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/analysis/next-experiments'), expect.objectContaining({ method: 'POST', body: JSON.stringify({ program_id: 'p1', limit: 5 }) }));
  });

  it('gets belief timeline by entity id', async () => {
    const fetchMock = mockFetch({ entity_id: 'h1', entity_type: 'hypothesis', points: [] });
    await analysisApi.beliefTimeline('h1');
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/analysis/belief-timeline/h1'), expect.objectContaining({ method: 'GET' }));
  });
});
