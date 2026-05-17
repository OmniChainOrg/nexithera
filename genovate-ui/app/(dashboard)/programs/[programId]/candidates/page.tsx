'use client';

import { CandidateKanban } from '@/components/candidates/candidate-kanban';
import { CreateCandidateForm } from '@/components/candidates/create-candidate-form';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { LoadingSpinner } from '@/components/common/loading-spinner';
import { EmptyState } from '@/components/common/empty-state';
import { useCandidates } from '@/lib/hooks/use-candidates';

export default function CandidatesPage({ params }: { params: { programId: string } }) {
  const { data, isLoading } = useCandidates(params.programId);

  return (
    <div className="space-y-6">
      <div className="overflow-x-auto">
        {isLoading ? (
          <LoadingSpinner />
        ) : !data?.length ? (
          <EmptyState title="No candidates yet" description="Create one to start the pipeline." />
        ) : (
          <CandidateKanban programId={params.programId} candidates={data} />
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">New candidate</CardTitle>
        </CardHeader>
        <CardContent>
          <CreateCandidateForm programId={params.programId} />
        </CardContent>
      </Card>
    </div>
  );
}
