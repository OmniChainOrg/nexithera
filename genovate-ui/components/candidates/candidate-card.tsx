import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { candidateStatusBg } from '@/lib/utils/colors';
import { formatScore, titleCase } from '@/lib/utils/formatters';
import type { Candidate } from '@/lib/types/genovate';

export function CandidateCard({ candidate }: { candidate: Candidate }) {
  return (
    <Card className="cursor-grab active:cursor-grabbing">
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold">{candidate.name}</div>
            <div className="truncate text-xs text-muted-foreground">
              {titleCase(candidate.candidate_type)}
              {candidate.target_name && ` · ${candidate.target_name}`}
            </div>
          </div>
          <span
            className={`h-2 w-2 shrink-0 rounded-full ${candidateStatusBg[candidate.status]}`}
            aria-hidden
          />
        </div>
      </CardHeader>
      <CardContent className="space-y-1 pt-0 text-xs">
        {candidate.mechanism_of_action && (
          <p className="line-clamp-2 text-muted-foreground">{candidate.mechanism_of_action}</p>
        )}
        <div className="flex items-center justify-between pt-1">
          <Badge variant="outline">{titleCase(candidate.therapeutic_area)}</Badge>
          <span className="font-mono">{formatScore(candidate.current_score)}</span>
        </div>
      </CardContent>
    </Card>
  );
}
