import Link from 'next/link';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { formatDate } from '@/lib/utils/formatters';
import type { Program } from '@/lib/types/genovate';

export function ProgramCard({ program }: { program: Program }) {
  return (
    <Link
      href={`/programs/${program.id}/overview`}
      className="block transition-transform hover:-translate-y-0.5"
    >
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between gap-2">
            <CardTitle className="truncate">{program.name}</CardTitle>
            <Badge variant={program.status === 'active' ? 'default' : 'secondary'}>
              {program.status}
            </Badge>
          </div>
          <CardDescription>{program.therapeutic_area}</CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          <p className="line-clamp-2">{program.description ?? 'No description.'}</p>
          <p className="mt-3 text-xs">Created {formatDate(program.created_at)}</p>
        </CardContent>
      </Card>
    </Link>
  );
}
