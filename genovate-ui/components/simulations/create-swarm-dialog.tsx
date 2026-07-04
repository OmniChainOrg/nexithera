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
import { useCreateSwarm, useCXUs } from '@/lib/hooks/use-simulations';

const SWARM_TYPES = ['cooperative', 'competitive', 'ensemble', 'adversarial'] as const;

interface FormValues {
  name: string;
  objective: string;
}

export function CreateSwarmDialog({ programId }: { programId: string }) {
  const [open, setOpen] = useState(false);
  const [swarmType, setSwarmType] = useState('');
  const [selectedCXUs, setSelectedCXUs] = useState<string[]>([]);
  const { register, handleSubmit, reset, formState } = useForm<FormValues>({
    defaultValues: { name: '', objective: '' },
  });
  const createSwarm = useCreateSwarm(programId);
  const cxus = useCXUs(programId);

  const toggleCXU = (id: string) =>
    setSelectedCXUs((prev) => (prev.includes(id) ? prev.filter((c) => c !== id) : [...prev, id]));

  const onSubmit = handleSubmit(async (values) => {
    await createSwarm.mutateAsync(
      {
        program_id: programId,
        objective: values.objective,
        swarm_config: {
          name: values.name,
          swarm_type: swarmType,
          cxu_ids: selectedCXUs,
        },
      },
      {
        onSuccess: () => {
          toast.success('Swarm created');
          reset();
          setSwarmType('');
          setSelectedCXUs([]);
          setOpen(false);
        },
        onError: (err) => toast.error(err instanceof Error ? err.message : 'Failed to create swarm'),
      },
    );
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline">Create Swarm</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New Swarm</DialogTitle>
          <DialogDescription>Create a multi-agent CXU swarm for coordinated simulation.</DialogDescription>
        </DialogHeader>
        <form onSubmit={onSubmit} className="space-y-3">
          <div>
            <label className="text-sm font-medium" htmlFor="swarm-name">Name</label>
            <Input id="swarm-name" {...register('name', { required: true })} placeholder="e.g. Swarm-01" />
          </div>
          <div>
            <label className="text-sm font-medium">Swarm type</label>
            <Select value={swarmType} onValueChange={setSwarmType} required>
              <SelectTrigger>
                <SelectValue placeholder="Select swarm type" />
              </SelectTrigger>
              <SelectContent>
                {SWARM_TYPES.map((t) => (
                  <SelectItem key={t} value={t}>{t}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="text-sm font-medium" htmlFor="swarm-objective">Objective</label>
            <Textarea
              id="swarm-objective"
              rows={2}
              {...register('objective', { required: true })}
              placeholder="Describe the swarm objective…"
            />
          </div>
          <div>
            <label className="text-sm font-medium">CXUs to include</label>
            {cxus.data?.length ? (
              <div className="mt-1 max-h-36 overflow-auto rounded-md border p-2 space-y-1">
                {cxus.data.map((c) => (
                  <label key={c.id} className="flex items-center gap-2 text-sm cursor-pointer">
                    <input
                      type="checkbox"
                      checked={selectedCXUs.includes(c.id)}
                      onChange={() => toggleCXU(c.id)}
                      className="accent-primary"
                    />
                    {c.name}
                  </label>
                ))}
              </div>
            ) : (
              <p className="mt-1 text-xs text-muted-foreground">No CXUs available — create some first.</p>
            )}
          </div>
          <DialogFooter>
            <Button
              type="submit"
              disabled={!swarmType || formState.isSubmitting || createSwarm.isPending}
            >
              {createSwarm.isPending ? 'Creating…' : 'Create swarm'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
