'use client';

import { useState } from 'react';
import { Clock, Thermometer } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { ProposedExperiment } from '@/lib/types/genovate';

export function ExperimentCard({ experiment, selected, onSelectedChange, onConduct, onDismiss, onCancel, onComplete, onView }: { experiment: ProposedExperiment; selected: boolean; onSelectedChange: (checked: boolean) => void; onConduct: () => void; onDismiss: () => void; onCancel: () => void; onComplete: () => void; onView: () => void }) {
  const [expanded, setExpanded] = useState(false);
  const gainColor = experiment.information_gain >= 0.7 ? 'text-green-600' : experiment.information_gain >= 0.4 ? 'text-amber-600' : 'text-red-600';
  return (
    <Card>
      <CardHeader className="space-y-2 pb-2">
        <div className="flex items-start gap-2">
          <input type="checkbox" checked={selected} onChange={(e) => onSelectedChange(e.target.checked)} className="mt-1" />
          <CardTitle className="text-sm leading-snug">{experiment.description}</CardTitle>
        </div>
      </CardHeader>
      <CardContent className="space-y-3 text-xs">
        <div className="flex flex-wrap items-center gap-2">
          <span className={`font-bold ${gainColor}`}>IG {experiment.information_gain.toFixed(2)}</span>
          <span className="inline-flex items-center gap-1"><Thermometer className="h-3 w-3" />${experiment.cost.toLocaleString()}</span>
          <span className="inline-flex items-center gap-1"><Clock className="h-3 w-3" />{experiment.duration_days}d</span>
          <Badge variant={experiment.priority === 1 ? 'destructive' : 'outline'}>P{experiment.priority}</Badge>
        </div>
        <button type="button" className="text-primary hover:underline" onClick={() => setExpanded((v) => !v)}>Expected outcomes</button>
        {expanded && <div className="space-y-1 rounded-md bg-muted p-2 text-muted-foreground"><p>Positive: {experiment.if_positive ?? '—'}</p><p>Negative: {experiment.if_negative ?? '—'}</p></div>}
        <div className="flex flex-wrap gap-2 pt-1">
          {experiment.status === 'proposed' && <><Button size="sm" onClick={onConduct}>Conduct</Button><Button size="sm" variant="outline" onClick={onDismiss}>Dismiss</Button></>}
          {experiment.status === 'in_progress' && <><Button size="sm" onClick={onComplete}>Mark Complete</Button><Button size="sm" variant="outline" onClick={onCancel}>Cancel</Button></>}
          {experiment.status === 'completed' && <Button size="sm" variant="outline" onClick={onView}>View Results</Button>}
        </div>
      </CardContent>
    </Card>
  );
}
