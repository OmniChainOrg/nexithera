'use client';

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
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
import { useCreateProgram } from '@/lib/hooks/use-programs';

const schema = z.object({
  name: z.string().min(2),
  therapeutic_area: z.string().min(2),
  description: z.string().optional(),
});

type FormValues = z.infer<typeof schema>;

export function CreateProgramDialog() {
  const [open, setOpen] = useState(false);
  const { register, handleSubmit, reset, formState } = useForm<FormValues>();
  const createProgram = useCreateProgram();

  const onSubmit = handleSubmit(async (values) => {
    const parsed = schema.safeParse(values);
    if (!parsed.success) return;
    await createProgram.mutateAsync(parsed.data);
    reset();
    setOpen(false);
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>Create program</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New program</DialogTitle>
          <DialogDescription>
            Programs scope all scientific work — evidence, hypotheses, candidates and reviews.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={onSubmit} className="space-y-3">
          <div>
            <label className="text-sm font-medium" htmlFor="name">
              Program name
            </label>
            <Input id="name" {...register('name', { required: true })} />
          </div>
          <div>
            <label className="text-sm font-medium" htmlFor="therapeutic_area">
              Therapeutic area
            </label>
            <Input id="therapeutic_area" {...register('therapeutic_area', { required: true })} />
          </div>
          <div>
            <label className="text-sm font-medium" htmlFor="description">
              Description
            </label>
            <Textarea id="description" rows={3} {...register('description')} />
          </div>
          <DialogFooter>
            <Button type="submit" disabled={formState.isSubmitting || createProgram.isPending}>
              {createProgram.isPending ? 'Creating…' : 'Create'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
