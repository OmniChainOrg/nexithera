'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import toast from 'react-hot-toast';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { candidatesApi } from '@/lib/api/candidates';
import type { DiscoveredTarget } from '@/lib/types/genovate';

export function CreateCandidateFromTargetDialog({
  target,
  programId,
  therapeuticArea,
  open,
  onOpenChange,
}: {
  target: DiscoveredTarget | null;
  programId: string;
  therapeuticArea?: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [name, setName] = useState(target?.target_name ?? '');
  const [moa, setMoa] = useState(target?.proposed_hypothesis ?? '');

  useEffect(() => {
    if (target && open) {
      setName(target.target_name);
      setMoa(target.proposed_hypothesis);
    }
  }, [target, open]);

  async function submit() {
    if (!target) return;
    setSubmitting(true);
    try {
      await candidatesApi.create({
        program_id: programId,
        name,
        candidate_type: 'gene_target',
        target_id: target.target_id ?? target.id ?? null,
        mechanism_of_action: moa,
        therapeutic_area: therapeuticArea ?? 'General',
      });
      toast.success('Candidate created');
      onOpenChange(false);
      router.push(`/programs/${programId}/candidates`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to create candidate');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create candidate</DialogTitle>
          <DialogDescription>Seed a candidate from the discovered target and hypothesis.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <label className="space-y-1 text-sm font-medium">
            Target
            <Input value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label className="space-y-1 text-sm font-medium">
            Hypothesis / mechanism
            <Textarea value={moa} onChange={(e) => setMoa(e.target.value)} rows={5} />
          </label>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button onClick={submit} disabled={submitting || !name}>Create Candidate</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
