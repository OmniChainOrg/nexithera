'use client';

import { useState } from 'react';
import { ReviewQueue } from '@/components/guardian/review-queue';
import { ReviewDecisionModal } from '@/components/guardian/review-decision-modal';
import { LoadingSpinner } from '@/components/common/loading-spinner';
import { useReviews } from '@/lib/hooks/use-reviews';

export default function GuardianQueuePage({ params }: { params: { programId: string } }) {
  const { data, isLoading } = useReviews({ program_id: params.programId, status: 'pending' });
  const [activeReviewId, setActiveReviewId] = useState<string | null>(null);

  return (
    <div className="space-y-4">
      {isLoading ? (
        <LoadingSpinner />
      ) : (
        <ReviewQueue
          reviews={data ?? []}
          hrefForReview={(r) => `#${r.id}`}
        />
      )}
      {data?.map((r) => (
        <button
          key={r.id}
          type="button"
          onClick={() => setActiveReviewId(r.id)}
          className="hidden"
        />
      ))}
      {activeReviewId && (
        <ReviewDecisionModal
          reviewId={activeReviewId}
          open
          onOpenChange={(o) => !o && setActiveReviewId(null)}
        />
      )}
    </div>
  );
}
