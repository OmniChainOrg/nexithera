'use client';

import { Card, CardContent } from '@/components/ui/card';
import { BulkReviewModal } from '@/components/guardian/bulk-review-modal';
import { useProgramStore } from '@/lib/stores/program-store';

export default function PipelineBulkPage() {
  const programId = useProgramStore((s) => s.currentProgramId);
  if (!programId) return <Card><CardContent className="p-6 text-sm text-muted-foreground">Select a program for bulk review.</CardContent></Card>;
  return <BulkReviewModal programId={programId} open onOpenChange={() => undefined} />;
}
