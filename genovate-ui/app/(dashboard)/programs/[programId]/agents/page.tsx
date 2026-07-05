'use client';

import { use, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { AgentRunList } from '@/components/agents/agent-run-list';
import { AgentRunDetail } from '@/components/agents/agent-run-detail';
import { RunAgentDialog } from '@/components/agents/run-agent-dialog';
import { LoadingSpinner } from '@/components/common/loading-spinner';
import { useAgentRuns } from '@/lib/hooks/use-agent-runs';
import type { AgentRun } from '@/lib/types/genovate';

export default function ProgramAgentsPage({
  params,
}: {
  params: Promise<{ programId: string }>;
}) {
  const { programId } = use(params);
  const { data, isLoading } = useAgentRuns({ program_id: programId, limit: 50 });
  const [selectedRun, setSelectedRun] = useState<AgentRun | null>(null);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Agent runs</h2>
        <RunAgentDialog programId={programId} />
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">History</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <LoadingSpinner />
          ) : (
            <AgentRunList
              runs={data ?? []}
              onRunClick={(run) => setSelectedRun(run)}
            />
          )}
        </CardContent>
      </Card>
      <AgentRunDetail run={selectedRun} onClose={() => setSelectedRun(null)} />
    </div>
  );
}
