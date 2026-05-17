'use client';

import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { LoadingSpinner } from '@/components/common/loading-spinner';
import { EmptyState } from '@/components/common/empty-state';
import { ProgramStats } from '@/components/programs/program-stats';
import { AgentRunList } from '@/components/agents/agent-run-list';
import { ReviewQueue } from '@/components/guardian/review-queue';
import { CreateProgramDialog } from '@/components/programs/create-program-dialog';
import { useProgramStore } from '@/lib/stores/program-store';
import { usePrograms } from '@/lib/hooks/use-programs';
import { useCandidates } from '@/lib/hooks/use-candidates';
import { useAgentRuns } from '@/lib/hooks/use-agent-runs';
import { useReviews } from '@/lib/hooks/use-reviews';
import { useSimulationRuns } from '@/lib/hooks/use-simulations';
import { candidateStatusOrder } from '@/lib/utils/colors';
import { titleCase } from '@/lib/utils/formatters';

export default function OverviewPage() {
  const programs = usePrograms();
  const currentProgramId = useProgramStore((s) => s.currentProgramId);

  const candidates = useCandidates(currentProgramId);
  const recentRuns = useAgentRuns({ program_id: currentProgramId ?? undefined, limit: 5 });
  const pendingReviews = useReviews({ program_id: currentProgramId ?? undefined, status: 'pending' });
  const activeSimulations = useSimulationRuns({
    program_id: currentProgramId ?? undefined,
    status: 'running',
  });

  if (programs.isLoading) return <LoadingSpinner />;
  if (programs.isError) {
    return (
      <EmptyState
        title="Could not load programs"
        description={
          (programs.error as Error).message ??
          'Confirm the Genovate API is running at NEXT_PUBLIC_API_URL.'
        }
      />
    );
  }
  if (!programs.data?.length) {
    return (
      <EmptyState
        title="No programs yet"
        description="Create your first program to start tracking evidence, candidates, and reviews."
        action={<CreateProgramDialog />}
      />
    );
  }

  const pipelineCounts = candidateStatusOrder.map((status) => ({
    status,
    count: candidates.data?.filter((c) => c.status === status).length ?? 0,
  }));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Overview</h1>
        <CreateProgramDialog />
      </div>

      <ProgramStats
        stats={[
          { label: 'Programs', value: programs.data?.length ?? 0 },
          { label: 'Active candidates', value: candidates.data?.length ?? 0 },
          {
            label: 'Pending reviews',
            value: pendingReviews.data?.length ?? 0,
            tone:
              (pendingReviews.data?.length ?? 0) > 0 ? 'warning' : 'default',
          },
          { label: 'Running simulations', value: activeSimulations.data?.length ?? 0 },
        ]}
      />

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">Candidate pipeline</CardTitle>
            {currentProgramId && (
              <Button asChild variant="ghost" size="sm">
                <Link href={`/programs/${currentProgramId}/candidates`}>Open kanban</Link>
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-8">
            {pipelineCounts.map((p) => (
              <div key={p.status} className="rounded-md border p-2 text-center">
                <div className="text-xs text-muted-foreground">{titleCase(p.status)}</div>
                <div className="mt-1 text-xl font-semibold">{p.count}</div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Recent agent runs</CardTitle>
          </CardHeader>
          <CardContent>
            {recentRuns.isLoading ? (
              <LoadingSpinner />
            ) : (
              <AgentRunList runs={recentRuns.data ?? []} />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Pending Guardian reviews</CardTitle>
          </CardHeader>
          <CardContent>
            {pendingReviews.isLoading ? (
              <LoadingSpinner />
            ) : (
              <ReviewQueue
                reviews={pendingReviews.data ?? []}
                hrefForReview={(r) =>
                  currentProgramId
                    ? `/programs/${currentProgramId}/guardian?review=${r.id}`
                    : `#`
                }
              />
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
