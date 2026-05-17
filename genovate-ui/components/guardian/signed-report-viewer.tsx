'use client';

import { useQuery } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { guardianApi } from '@/lib/api/guardian';
import { ExternalLink, FileText } from 'lucide-react';

export function SignedReportViewer({ reviewId }: { reviewId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ['guardian', 'signed-report', reviewId],
    queryFn: ({ signal }) => guardianApi.signedReport(reviewId, signal),
    enabled: !!reviewId,
  });

  if (isLoading) return <p className="text-sm text-muted-foreground">Generating report…</p>;
  if (!data?.url) {
    return (
      <p className="text-sm text-muted-foreground">
        No signed report yet for this review.
      </p>
    );
  }

  return (
    <div className="flex items-center gap-2 rounded-lg border p-3">
      <FileText className="h-5 w-5 text-muted-foreground" />
      <div className="flex-1 text-sm">
        <p className="font-medium">Signed Guardian report</p>
        <p className="text-xs text-muted-foreground">PDF, cryptographically signed</p>
      </div>
      <Button asChild variant="outline" size="sm">
        <a href={data.url} target="_blank" rel="noreferrer noopener">
          Open <ExternalLink className="ml-1 h-3 w-3" />
        </a>
      </Button>
    </div>
  );
}
