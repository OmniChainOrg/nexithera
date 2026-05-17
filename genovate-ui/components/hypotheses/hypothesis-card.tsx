import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ConfidenceBadge } from '@/lib/utils/confidence-badge';
import { formatRelative, titleCase } from '@/lib/utils/formatters';
import type { Hypothesis, HypothesisStatus } from '@/lib/types/genovate';

const statusVariant: Record<HypothesisStatus, 'default' | 'secondary' | 'destructive' | 'outline'> = {
  draft: 'outline',
  under_review: 'secondary',
  supported: 'default',
  refuted: 'destructive',
  deprecated: 'outline',
};

export function HypothesisCard({ hypothesis }: { hypothesis: Hypothesis }) {
  const total = hypothesis.supporting_evidence_count + hypothesis.contradicting_evidence_count;
  const supportPct = total === 0 ? 0 : hypothesis.supporting_evidence_count / total;

  return (
    <Card>
      <CardHeader className="space-y-1">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-sm font-medium leading-snug">{hypothesis.text}</CardTitle>
          <ConfidenceBadge confidence={hypothesis.confidence} />
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Badge variant={statusVariant[hypothesis.status]}>{titleCase(hypothesis.status)}</Badge>
          <span>v{hypothesis.version}</span>
          <span>· {titleCase(hypothesis.claim_type)}</span>
          <span>· Updated {formatRelative(hypothesis.updated_at)}</span>
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        <div
          className="h-2 w-full overflow-hidden rounded-full bg-destructive/20"
          aria-label={`${Math.round(supportPct * 100)}% supporting evidence`}
        >
          <div
            className="h-full bg-confidence-high"
            style={{ width: `${Math.round(supportPct * 100)}%` }}
          />
        </div>
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>{hypothesis.supporting_evidence_count} supporting</span>
          <span>{hypothesis.contradicting_evidence_count} contradicting</span>
        </div>
      </CardContent>
    </Card>
  );
}
