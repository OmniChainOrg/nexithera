'use client';

import { useMemo, useState } from 'react';
import toast from 'react-hot-toast';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Textarea } from '@/components/ui/textarea';
import { useGuardianBulk } from '@/lib/hooks/use-guardian-bulk';
import { useReviews } from '@/lib/hooks/use-reviews';
import type { GuardianBulkAction, GuardianReview } from '@/lib/types/genovate';

function recommendation(review: GuardianReview): string {
  return review.decision || review.risk_flags[0]?.flag || '—';
}

export function BulkReviewModal({ programId, open, onOpenChange }: { programId: string; open: boolean; onOpenChange: (open: boolean) => void }) {
  const { data = [] } = useReviews({ program_id: programId, status: 'pending' });
  const [selected, setSelected] = useState<string[]>([]);
  const [note, setNote] = useState('');
  const [action, setAction] = useState<GuardianBulkAction | null>(null);
  const bulk = useGuardianBulk(programId);
  const selectedReviews = useMemo(() => data.filter((r) => selected.includes(r.id)), [data, selected]);
  const selectAbove = () => setSelected(data.filter((r) => r.risk_flags.some((f) => f.severity !== 'low')).map((r) => r.id));
  const run = () => {
    if (!action) return;
    bulk.mutate({ action, review_ids: selected, note }, { onSuccess: (res) => { toast.success(`Bulk ${action} complete`); setSelected([]); setAction(null); if (!res.failed_ids.length) onOpenChange(false); } });
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-5xl">
        <DialogHeader><DialogTitle>Bulk Guardian Actions</DialogTitle><DialogDescription>Apply one decision to selected pending Guardian reviews.</DialogDescription></DialogHeader>
        <div className="flex flex-wrap gap-2"><Button variant="outline" onClick={() => setSelected(data.map((r) => r.id))}>Select All</Button><Button variant="outline" onClick={selectAbove}>Select Above 0.7</Button><Button variant="outline" onClick={() => setSelected([])}>Clear</Button></div>
        <div className="max-h-96 overflow-auto rounded-lg border">
          <table className="w-full text-sm"><thead className="bg-muted"><tr><th className="p-2 text-left">Pick</th><th className="p-2 text-left">Entity</th><th className="p-2 text-left">Recommendation</th><th className="p-2 text-left" title="Scorecard overall is unavailable from this review object">Score</th><th className="p-2 text-left">Risk flags</th></tr></thead><tbody>{data.map((r) => <tr key={r.id} className="border-t"><td className="p-2"><input type="checkbox" checked={selected.includes(r.id)} onChange={(e) => setSelected((prev) => e.target.checked ? [...prev, r.id] : prev.filter((id) => id !== r.id))} /></td><td className="p-2 font-mono text-xs">{r.entity_id}</td><td className="p-2">{recommendation(r)}</td><td className="p-2" title="Scorecard overall is unavailable from the review object">—</td><td className="p-2">{r.risk_flags.map((f) => f.flag).join(', ') || '—'}</td></tr>)}</tbody></table>
        </div>
        <Textarea placeholder="Optional note" value={note} onChange={(e) => setNote(e.target.value)} />
        {action && <div className="rounded-md border p-3 text-sm">Confirm {action} for {selectedReviews.length} reviews?</div>}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Close</Button>
          {(['approve', 'kill', 'park'] as GuardianBulkAction[]).map((a) => <Button key={a} variant={a === 'kill' ? 'destructive' : 'default'} disabled={!selected.length || bulk.isPending} onClick={() => action === a ? run() : setAction(a)}>{action === a ? `Confirm ${a}` : a}</Button>)}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
