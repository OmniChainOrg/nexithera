'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { AgentRunList } from '@/components/agents/agent-run-list';
import { RunAgentDialog } from '@/components/agents/run-agent-dialog';
import { LoadingSpinner } from '@/components/common/loading-spinner';
import { useAgentRuns } from '@/lib/hooks/use-agent-runs';

export default function ProgramAgentsPage({ params }: { params: { programId: string } }) {
  const { data, isLoading } = useAgentRuns({ program_id: params.programId, limit: 50 });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Agent runs</h2>
        <RunAgentDialog programId={params.programId} />
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">History</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? <LoadingSpinner /> : <AgentRunList runs={data ?? []} />}
        </CardContent>
      </Card>
    </div>
  );
}
