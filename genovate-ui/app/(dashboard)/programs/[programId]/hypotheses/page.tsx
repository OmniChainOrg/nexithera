'use client';

import { HypothesisCard } from '@/components/hypotheses/hypothesis-card';
import { CreateHypothesisForm } from '@/components/hypotheses/create-hypothesis-form';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { LoadingSpinner } from '@/components/common/loading-spinner';
import { EmptyState } from '@/components/common/empty-state';
import { useHypotheses } from '@/lib/hooks/use-hypotheses';

export default function HypothesisWorkspacePage({
  params,
}: {
  params: { programId: string };
}) {
  const { data, isLoading } = useHypotheses(params.programId);

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
      <div className="space-y-3">
        {isLoading ? (
          <LoadingSpinner />
        ) : !data?.length ? (
          <EmptyState title="No hypotheses" description="Create your first hypothesis to begin." />
        ) : (
          data.map((h) => <HypothesisCard key={h.id} hypothesis={h} />)
        )}
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">New hypothesis</CardTitle>
        </CardHeader>
        <CardContent>
          <CreateHypothesisForm programId={params.programId} />
        </CardContent>
      </Card>
    </div>
  );
}
