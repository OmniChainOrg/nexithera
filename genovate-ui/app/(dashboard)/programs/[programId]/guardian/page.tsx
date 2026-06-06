'use client';

import { use, useState } from 'react';
import { Button } from '@/components/ui/button';
import { ReviewQueue } from '@/components/guardian/review-queue';
import { ReviewDecisionModal } from '@/components/guardian/review-decision-modal';
import { BulkReviewModal } from '@/components/guardian/bulk-review-modal';
import { LoadingSpinner } from '@/components/common/loading-spinner';
import { useReviews } from '@/lib/hooks/use-reviews';

export default function GuardianQueuePage({ params }: { params: Promise<{ programId: string }> }) {
  const { programId } = use(params);
  const { data, isLoading } = useReviews({ program_id: programId, status: 'pending' });
  const [activeReviewId, setActiveReviewId] = useState<string | null>(null);
  const [bulkOpen, setBulkOpen] = useState(false);

  return (
    <div className="space-y-4">
      <div className="flex justify-end"><Button onClick={() => setBulkOpen(true)}>Bulk Review</Button></div>
      {isLoading ? <LoadingSpinner /> : <ReviewQueue reviews={data ?? []} hrefForReview={(r) => `#${r.id}`} />}
      {data?.map((r) => <button key={r.id} type="button" onClick={() => setActiveReviewId(r.id)} className="hidden" />)}
      {activeReviewId && <ReviewDecisionModal reviewId={activeReviewId} open onOpenChange={(o) => !o && setActiveReviewId(null)} />}
      <BulkReviewModal programId={programId} open={bulkOpen} onOpenChange={setBulkOpen} />
    </div>
  );
}
