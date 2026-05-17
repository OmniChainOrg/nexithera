import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils/cn';

interface StatProps {
  label: string;
  value: string | number;
  hint?: string;
  tone?: 'default' | 'success' | 'warning' | 'danger';
}

const toneClass: Record<NonNullable<StatProps['tone']>, string> = {
  default: 'text-foreground',
  success: 'text-confidence-high',
  warning: 'text-confidence-medium',
  danger: 'text-confidence-low',
};

export function ProgramStats({ stats }: { stats: StatProps[] }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
      {stats.map((s) => (
        <Card key={s.label}>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              {s.label}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className={cn('text-2xl font-semibold', toneClass[s.tone ?? 'default'])}>
              {s.value}
            </div>
            {s.hint && <p className="mt-1 text-xs text-muted-foreground">{s.hint}</p>}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
