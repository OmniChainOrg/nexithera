'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Textarea } from '@/components/ui/textarea';
import { useSubmitReviewDecision } from '@/lib/hooks/use-reviews';
import type { GuardianDecision } from '@/lib/types/genovate';

const DECISIONS: { value: GuardianDecision; label: string; variant?: 'destructive' | 'default' }[] = [
  { value: 'approve', label: 'Approve' },
  { value: 'request_revision', label: 'Request revision' },
  { value: 'escalate', label: 'Escalate' },
  { value: 'park', label: 'Park' },
  { value: 'kill', label: 'Kill', variant: 'destructive' },
  { value: 'promote_epistemicos', label: 'Promote to EpistemicOS' },
];

interface ReviewDecisionModalProps {
  reviewId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ReviewDecisionModal({ reviewId, open, onOpenChange }: ReviewDecisionModalProps) {
  const [decision, setDecision] = useState<GuardianDecision | null>(null);
  const [rationale, setRationale] = useState('');
  const submit = useSubmitReviewDecision();

  const onSubmit = async () => {
    if (!decision || !rationale.trim()) return;
    await submit.mutateAsync({
      id: reviewId,
      input: { decision, decision_rationale: rationale.trim() },
    });
    onOpenChange(false);
    setDecision(null);
    setRationale('');
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Guardian decision</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2">
            {DECISIONS.map((d) => (
              <Button
                key={d.value}
                size="sm"
                variant={decision === d.value ? 'default' : d.variant ?? 'outline'}
                onClick={() => setDecision(d.value)}
              >
                {d.label}
              </Button>
            ))}
          </div>
          <div>
            <label className="text-sm font-medium" htmlFor="rationale">
              Rationale (required)
            </label>
            <Textarea
              id="rationale"
              rows={4}
              value={rationale}
              onChange={(e) => setRationale(e.target.value)}
              required
            />
          </div>
        </div>
        <DialogFooter>
          <Button onClick={onSubmit} disabled={!decision || !rationale.trim() || submit.isPending}>
            {submit.isPending ? 'Submitting…' : 'Submit decision'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
