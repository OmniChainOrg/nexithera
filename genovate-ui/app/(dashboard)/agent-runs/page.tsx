'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { AgentRunList } from '@/components/agents/agent-run-list';
import { LoadingSpinner } from '@/components/common/loading-spinner';
import { useAgentRuns } from '@/lib/hooks/use-agent-runs';

export default function GlobalAgentRunsPage() {
  const { data, isLoading } = useAgentRuns({ limit: 100 });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">All agent runs</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? <LoadingSpinner /> : <AgentRunList runs={data ?? []} />}
      </CardContent>
    </Card>
  );
}
