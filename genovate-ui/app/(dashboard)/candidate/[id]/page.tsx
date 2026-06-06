'use client';

import { use } from 'react';
import Link from 'next/link';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { LoadingSpinner } from '@/components/common/loading-spinner';
import { EmptyState } from '@/components/common/empty-state';
import { useCandidate } from '@/lib/hooks/use-candidates';
import { PartnerabilityTab } from '@/components/candidates/partnerability-tab';
import { INDReadinessTab } from '@/components/candidates/ind-readiness-tab';
import { PatentMapTab } from '@/components/candidates/patent-map-tab';

export default function CandidateDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { data: candidate, isLoading } = useCandidate(id);

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <LoadingSpinner />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-baseline justify-between gap-2">
        <div>
          <h1 className="text-3xl font-bold">{candidate?.name ?? 'Candidate'}</h1>
          {candidate?.program_id && (
            <Link
              href={`/programs/${candidate.program_id}/candidates`}
              className="text-sm text-primary underline"
            >
              ← Back to program
            </Link>
          )}
        </div>
      </div>

      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList className="flex flex-wrap">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="evidence">Evidence</TabsTrigger>
          <TabsTrigger value="simulations">Simulations</TabsTrigger>
          <TabsTrigger value="guardian">Guardian</TabsTrigger>
          <TabsTrigger value="settings">Settings</TabsTrigger>
          <TabsTrigger value="partnerability">Partnerability</TabsTrigger>
          <TabsTrigger value="ind-readiness">IND Readiness</TabsTrigger>
          <TabsTrigger value="patent-map">Patent Map</TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <CandidateOverview candidate={candidate} />
        </TabsContent>
        {(['evidence', 'simulations', 'guardian', 'settings'] as const).map((tab) => (
          <TabsContent key={tab} value={tab}>
            <EmptyState
              title={`${tab[0].toUpperCase()}${tab.slice(1)}`}
              description={`See the existing ${tab} dashboard under the program for this candidate.`}
            />
          </TabsContent>
        ))}

        <TabsContent value="partnerability">
          <PartnerabilityTab
            candidateId={id}
            candidateName={candidate?.name}
            candidatePhase={candidate?.status ?? undefined}
          />
        </TabsContent>
        <TabsContent value="ind-readiness">
          <INDReadinessTab
            candidateId={id}
            programId={candidate?.program_id ?? undefined}
          />
        </TabsContent>
        <TabsContent value="patent-map">
          <PatentMapTab candidateId={id} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function CandidateOverview({ candidate }: { candidate: ReturnType<typeof useCandidate>['data'] }) {
  if (!candidate) {
    return (
      <EmptyState
        title="Candidate not found"
        description="The candidate may have been deleted or you may not have access."
      />
    );
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle>{candidate.name}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        <p>
          <strong>Status:</strong> {candidate.status}
        </p>
        <p>
          <strong>Type:</strong> {candidate.candidate_type}
        </p>
        {candidate.therapeutic_area && (
          <p>
            <strong>Therapeutic area:</strong> {candidate.therapeutic_area}
          </p>
        )}
        {candidate.mechanism_of_action && (
          <p>
            <strong>Mechanism:</strong> {candidate.mechanism_of_action}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
