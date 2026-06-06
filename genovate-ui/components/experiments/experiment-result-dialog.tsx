'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import type { ExperimentOutcome, ProposedExperiment } from '@/lib/types/genovate';

export function ExperimentResultDialog({ experiment, open, readOnly, onOpenChange, onSubmit }: { experiment: ProposedExperiment | null; open: boolean; readOnly?: boolean; onOpenChange: (open: boolean) => void; onSubmit: (outcome: ExperimentOutcome) => void }) {
  const [result, setResult] = useState<ExperimentOutcome['result']>('positive');
  const [notes, setNotes] = useState('');
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader><DialogTitle>{readOnly ? 'Experiment results' : 'Record experiment outcome'}</DialogTitle></DialogHeader>
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">{experiment?.description}</p>
          <Select value={result} onValueChange={(v) => setResult(v as ExperimentOutcome['result'])} disabled={readOnly}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="positive">Positive</SelectItem><SelectItem value="negative">Negative</SelectItem><SelectItem value="inconclusive">Inconclusive</SelectItem></SelectContent>
          </Select>
          <Textarea placeholder="Notes" value={notes} onChange={(e) => setNotes(e.target.value)} readOnly={readOnly} />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>{readOnly ? 'Close' : 'Cancel'}</Button>
          {!readOnly && experiment && <Button onClick={() => onSubmit({ experiment_id: experiment.id, result, notes })}>Save result</Button>}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
