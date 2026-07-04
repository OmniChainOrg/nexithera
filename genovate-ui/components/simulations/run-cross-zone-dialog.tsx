'use client';

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import toast from 'react-hot-toast';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useRunCrossZone, useZones } from '@/lib/hooks/use-simulations';

const EXAMPLE_COUPLING = JSON.stringify(
  { signaling_output: 'drug_concentration_input' },
  null,
  2,
);

interface FormValues {
  coupling_map: string;
  inputs: string;
}

export function RunCrossZoneDialog({ programId }: { programId: string }) {
  const [open, setOpen] = useState(false);
  const [sourceZoneId, setSourceZoneId] = useState('');
  const [targetZoneId, setTargetZoneId] = useState('');
  const { register, handleSubmit, reset, formState } = useForm<FormValues>({
    defaultValues: { coupling_map: EXAMPLE_COUPLING, inputs: '{}' },
  });
  const runCrossZone = useRunCrossZone(programId);
  const zones = useZones(programId);

  const onSubmit = handleSubmit(async (values) => {
    let coupling_map: Record<string, string> = {};
    let inputs: Record<string, unknown> = {};
    try {
      coupling_map = JSON.parse(values.coupling_map || '{}');
    } catch {
      toast.error('Coupling map must be valid JSON');
      return;
    }
    try {
      inputs = JSON.parse(values.inputs || '{}');
    } catch {
      toast.error('Input state must be valid JSON');
      return;
    }
    await runCrossZone.mutateAsync(
      { source_zone_id: sourceZoneId, target_zone_id: targetZoneId, coupling_map, inputs, program_id: programId },
      {
        onSuccess: () => {
          toast.success('Cross-zone run started');
          reset();
          setSourceZoneId('');
          setTargetZoneId('');
          setOpen(false);
        },
        onError: (err) => toast.error(err instanceof Error ? err.message : 'Failed to start cross-zone run'),
      },
    );
  });

  const zoneList = zones.data ?? [];

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline">Run Cross-Zone</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Run Cross-Zone Simulation</DialogTitle>
          <DialogDescription>Couple two zones and run a cross-zone simulation via EpistemicOS.</DialogDescription>
        </DialogHeader>
        <form onSubmit={onSubmit} className="space-y-3">
          <div>
            <label className="text-sm font-medium">Source zone</label>
            <Select value={sourceZoneId} onValueChange={setSourceZoneId} required>
              <SelectTrigger>
                <SelectValue placeholder={zoneList.length ? 'Select source zone' : 'No zones available'} />
              </SelectTrigger>
              <SelectContent>
                {zoneList.map((z) => (
                  <SelectItem key={z.id} value={z.id}>{z.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="text-sm font-medium">Target zone</label>
            <Select value={targetZoneId} onValueChange={setTargetZoneId} required>
              <SelectTrigger>
                <SelectValue placeholder={zoneList.length ? 'Select target zone' : 'No zones available'} />
              </SelectTrigger>
              <SelectContent>
                {zoneList.map((z) => (
                  <SelectItem key={z.id} value={z.id}>{z.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="text-sm font-medium" htmlFor="coupling-map">Coupling map JSON</label>
            <Textarea id="coupling-map" rows={3} {...register('coupling_map')} />
          </div>
          <div>
            <label className="text-sm font-medium" htmlFor="xz-inputs">Input state JSON (optional)</label>
            <Textarea id="xz-inputs" rows={2} {...register('inputs')} placeholder="{}" />
          </div>
          <DialogFooter>
            <Button
              type="submit"
              disabled={!sourceZoneId || !targetZoneId || formState.isSubmitting || runCrossZone.isPending}
            >
              {runCrossZone.isPending ? 'Running…' : 'Run simulation'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
