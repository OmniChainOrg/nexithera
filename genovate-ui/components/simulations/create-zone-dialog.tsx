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
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useCreateZone } from '@/lib/hooks/use-simulations';

const ZONE_TYPES = [
  'tumor_microenvironment',
  'pkpd',
  'pathway_signaling',
  'immune_response',
  'resistance_evolution',
  'dose_response',
] as const;

interface FormValues {
  zone_type: string;
  name: string;
  config: string;
}

export function CreateZoneDialog({ programId }: { programId: string }) {
  const [open, setOpen] = useState(false);
  const [zoneType, setZoneType] = useState('');
  const { register, handleSubmit, reset, formState } = useForm<FormValues>({
    defaultValues: { name: '', config: '{}' },
  });
  const createZone = useCreateZone(programId);

  const onSubmit = handleSubmit(async (values) => {
    let config: Record<string, unknown> = {};
    try {
      config = JSON.parse(values.config || '{}');
    } catch {
      toast.error('Config must be valid JSON');
      return;
    }
    await createZone.mutateAsync(
      { program_id: programId, zone_type: zoneType, name: values.name || undefined, config },
      {
        onSuccess: () => {
          toast.success('Zone created');
          reset();
          setZoneType('');
          setOpen(false);
        },
        onError: (err) => toast.error(err instanceof Error ? err.message : 'Failed to create zone'),
      },
    );
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline">Create Zone</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New Zone</DialogTitle>
          <DialogDescription>Create a simulation zone in EpistemicOS.</DialogDescription>
        </DialogHeader>
        <form onSubmit={onSubmit} className="space-y-3">
          <div>
            <label className="text-sm font-medium">Zone type</label>
            <Select value={zoneType} onValueChange={setZoneType} required>
              <SelectTrigger>
                <SelectValue placeholder="Select zone type" />
              </SelectTrigger>
              <SelectContent>
                {ZONE_TYPES.map((t) => (
                  <SelectItem key={t} value={t}>{t.replace(/_/g, ' ')}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="text-sm font-medium" htmlFor="zone-name">Name (optional)</label>
            <Input id="zone-name" {...register('name')} placeholder="e.g. TME Zone A" />
          </div>
          <div>
            <label className="text-sm font-medium" htmlFor="zone-config">Config JSON (optional)</label>
            <Textarea id="zone-config" rows={3} {...register('config')} placeholder="{}" />
          </div>
          <DialogFooter>
            <Button type="submit" disabled={!zoneType || formState.isSubmitting || createZone.isPending}>
              {createZone.isPending ? 'Creating…' : 'Create zone'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
