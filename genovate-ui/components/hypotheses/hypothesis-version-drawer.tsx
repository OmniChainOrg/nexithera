'use client';

import toast from 'react-hot-toast';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { HypothesisVersionTimeline } from '@/components/hypotheses/hypothesis-version-timeline';
import { useHypothesisVersions } from '@/lib/hooks/use-hypotheses';

export function HypothesisVersionDrawer({ hypothesisId, open, onOpenChange, onRestore }: { hypothesisId: string | null; open: boolean; onOpenChange: (open: boolean) => void; onRestore?: () => void }) {
  const { data } = useHypothesisVersions(hypothesisId);
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader><DialogTitle>Hypothesis timeline</DialogTitle></DialogHeader>
        <HypothesisVersionTimeline versions={data ?? []} />
        <DialogFooter><Button onClick={() => onRestore ? onRestore() : toast('Restore not yet wired')}>Restore</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
