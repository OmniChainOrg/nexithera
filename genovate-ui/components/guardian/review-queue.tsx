import Link from 'next/link';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { formatRelative, titleCase } from '@/lib/utils/formatters';
import type { GuardianReview } from '@/lib/types/genovate';

export function ReviewQueue({
  reviews,
  hrefForReview,
}: {
  reviews: GuardianReview[];
  hrefForReview?: (r: GuardianReview) => string;
}) {
  if (!reviews.length) {
    return <p className="p-6 text-center text-sm text-muted-foreground">No pending reviews.</p>;
  }
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {reviews.map((r) => {
        const inner = (
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-medium">
                  {titleCase(r.review_type)}
                </CardTitle>
                <Badge variant="secondary">{titleCase(r.entity_type)}</Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-1 text-xs text-muted-foreground">
              <div>Entity: <span className="font-mono">{r.entity_id}</span></div>
              <div>Reviewer: {r.reviewer_email || '—'}</div>
              <div>Updated {formatRelative(r.reviewed_at)}</div>
              {r.risk_flags.length > 0 && (
                <div className="flex flex-wrap gap-1 pt-1">
                  {r.risk_flags.slice(0, 3).map((f, i) => (
                    <Badge
                      key={i}
                      variant={f.severity === 'high' ? 'destructive' : 'outline'}
                      className="text-[10px]"
                    >
                      {f.flag}
                    </Badge>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        );
        return hrefForReview ? (
          <Link key={r.id} href={hrefForReview(r)}>
            {inner}
          </Link>
        ) : (
          <div key={r.id}>{inner}</div>
        );
      })}
    </div>
  );
}
