'use client';

import { use } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { CXUStatusCard } from '@/components/simulations/cxu-status-card';
import { SwarmVisualization } from '@/components/simulations/swarm-visualization';
import { CrossZoneViewer } from '@/components/simulations/cross-zone-viewer';
import { LoadingSpinner } from '@/components/common/loading-spinner';
import { EmptyState } from '@/components/common/empty-state';
import {
  useCXUs,
  useSimulationRuns,
  useZones,
} from '@/lib/hooks/use-simulations';

export default function SimulationDashboardPage({
  params,
}: {
  params: Promise<{ programId: string }>;
}) {
  const { programId } = use(params);
  const zones = useZones(programId);
  const cxus = useCXUs(programId);
  const runs = useSimulationRuns({ program_id: programId, limit: 20 });

  const swarmMembers = (cxus.data ?? []).slice(0, 8).map((c) => ({
    id: c.id,
    consensus: Math.min(1, Math.max(0, (c.metrics?.consensus as number | undefined) ?? 0.5)),
    label: c.name,
  }));
  const consensus =
    swarmMembers.length === 0
      ? 0
      : swarmMembers.reduce((acc, m) => acc + m.consensus, 0) / swarmMembers.length;

  return (
    <div className="space-y-6">
      <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">CXUs</CardTitle>
          </CardHeader>
          <CardContent>
            {cxus.isLoading ? (
              <LoadingSpinner />
            ) : !cxus.data?.length ? (
              <EmptyState title="No CXUs" description="Create one to begin simulation." />
            ) : (
              <div className="grid gap-3 sm:grid-cols-2">
                {cxus.data.map((c) => (
                  <CXUStatusCard key={c.id} cxu={c} />
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Swarm consensus</CardTitle>
          </CardHeader>
          <CardContent>
            <SwarmVisualization members={swarmMembers} consensus={consensus} />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Zones</CardTitle>
        </CardHeader>
        <CardContent>
          {zones.isLoading ? (
            <LoadingSpinner />
          ) : !zones.data?.length ? (
            <p className="text-sm text-muted-foreground">No zones configured.</p>
          ) : (
            <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {zones.data.map((z) => (
                <li key={z.id} className="flex items-center justify-between rounded-md border p-2 text-sm">
                  <span>{z.name}</span>
                  <span className="text-xs text-muted-foreground">{z.status}</span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Cross-zone runs</CardTitle>
        </CardHeader>
        <CardContent>
          {runs.isLoading ? <LoadingSpinner /> : <CrossZoneViewer runs={runs.data ?? []} />}
        </CardContent>
      </Card>
    </div>
  );
}
