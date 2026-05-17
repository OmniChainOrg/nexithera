'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ProgramStats } from '@/components/programs/program-stats';
import { LoadingSpinner } from '@/components/common/loading-spinner';
import { useCandidates } from '@/lib/hooks/use-candidates';
import { useAgentRuns } from '@/lib/hooks/use-agent-runs';
import { useReviews } from '@/lib/hooks/use-reviews';
import { useSimulationRuns } from '@/lib/hooks/use-simulations';
import { AgentRunList } from '@/components/agents/agent-run-list';

export default function ProgramOverviewPage({
  params,
}: {
  params: { programId: string };
}) {
  const programId = params.programId;
  const candidates = useCandidates(programId);
  const runs = useAgentRuns({ program_id: programId, limit: 5 });
  const reviews = useReviews({ program_id: programId, status: 'pending' });
  const sims = useSimulationRuns({ program_id: programId, status: 'running' });

  return (
    <div className="space-y-6">
      <ProgramStats
        stats={[
          { label: 'Candidates', value: candidates.data?.length ?? 0 },
          {
            label: 'Pending reviews',
            value: reviews.data?.length ?? 0,
            tone: (reviews.data?.length ?? 0) > 0 ? 'warning' : 'default',
          },
          { label: 'Running simulations', value: sims.data?.length ?? 0 },
          { label: 'Recent agent runs', value: runs.data?.length ?? 0 },
        ]}
      />
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Recent agent activity</CardTitle>
        </CardHeader>
        <CardContent>
          {runs.isLoading ? <LoadingSpinner /> : <AgentRunList runs={runs.data ?? []} />}
        </CardContent>
      </Card>
    </div>
  );
}
