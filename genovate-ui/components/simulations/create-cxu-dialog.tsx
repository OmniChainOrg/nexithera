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
import { useCreateCXU, useZones } from '@/lib/hooks/use-simulations';

const CXU_TYPES = [
  'tumor_microenvironment',
  'pkpd',
  'pathway_signaling',
  'immune_response',
  'resistance_evolution',
  'dose_response',
] as const;

interface FormValues {
  name: string;
  configuration: string;
}

export function CreateCXUDialog({ programId }: { programId: string }) {
  const [open, setOpen] = useState(false);
  const [cxuType, setCxuType] = useState('');
  const [zoneId, setZoneId] = useState('');
  const { register, handleSubmit, reset, formState } = useForm<FormValues>({
    defaultValues: { name: '', configuration: '{}' },
  });
  const createCXU = useCreateCXU(programId);
  const zones = useZones(programId);

  const onSubmit = handleSubmit(async (values) => {
    let configuration: Record<string, unknown> = {};
    try {
      configuration = JSON.parse(values.configuration || '{}');
    } catch {
      toast.error('Configuration must be valid JSON');
      return;
    }
    await createCXU.mutateAsync(
      { zone_id: zoneId, cxu_type: cxuType, configuration, program_id: programId },
      {
        onSuccess: () => {
          toast.success('CXU created');
          reset();
          setCxuType('');
          setZoneId('');
          setOpen(false);
        },
        onError: (err) => toast.error(err instanceof Error ? err.message : 'Failed to create CXU'),
      },
    );
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline">Create CXU</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New CXU</DialogTitle>
          <DialogDescription>Create a Causal Experience Unit inside a zone.</DialogDescription>
        </DialogHeader>
        <form onSubmit={onSubmit} className="space-y-3">
          <div>
            <label className="text-sm font-medium" htmlFor="cxu-name">Name</label>
            <Input id="cxu-name" {...register('name', { required: true })} placeholder="e.g. CXU-001" />
          </div>
          <div>
            <label className="text-sm font-medium">CXU type</label>
            <Select value={cxuType} onValueChange={setCxuType} required>
              <SelectTrigger>
                <SelectValue placeholder="Select CXU type" />
              </SelectTrigger>
              <SelectContent>
                {CXU_TYPES.map((t) => (
                  <SelectItem key={t} value={t}>{t.replace(/_/g, ' ')}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="text-sm font-medium">Zone</label>
            <Select value={zoneId} onValueChange={setZoneId} required>
              <SelectTrigger>
                <SelectValue placeholder={zones.data?.length ? 'Select zone' : 'No zones — create one first'} />
              </SelectTrigger>
              <SelectContent>
                {(zones.data ?? []).map((z) => (
                  <SelectItem key={z.id} value={z.id}>{z.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="text-sm font-medium" htmlFor="cxu-config">Configuration JSON (optional)</label>
            <Textarea id="cxu-config" rows={3} {...register('configuration')} placeholder="{}" />
          </div>
          <DialogFooter>
            <Button
              type="submit"
              disabled={!cxuType || !zoneId || formState.isSubmitting || createCXU.isPending}
            >
              {createCXU.isPending ? 'Creating…' : 'Create CXU'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
