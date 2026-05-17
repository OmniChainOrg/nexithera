'use client';

import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { api } from '@/lib/api/client';
import type { Hypothesis } from '@/lib/types/genovate';

const schema = z.object({
  text: z.string().min(10),
  claim_type: z.string().min(2),
});

interface CreateHypothesisFormProps {
  programId: string;
  onCreated?: (h: Hypothesis) => void;
}

export function CreateHypothesisForm({ programId, onCreated }: CreateHypothesisFormProps) {
  const { register, handleSubmit, reset, formState } = useForm<z.infer<typeof schema>>();

  const onSubmit = handleSubmit(async (values) => {
    const parsed = schema.safeParse(values);
    if (!parsed.success) return;
    const created = await api.post<Hypothesis>('/hypotheses', {
      program_id: programId,
      ...parsed.data,
    });
    reset();
    onCreated?.(created);
  });

  return (
    <form onSubmit={onSubmit} className="space-y-3">
      <div>
        <label className="text-sm font-medium" htmlFor="text">
          Hypothesis statement
        </label>
        <Textarea id="text" rows={3} {...register('text', { required: true })} />
      </div>
      <div>
        <label className="text-sm font-medium" htmlFor="claim_type">
          Claim type
        </label>
        <Input
          id="claim_type"
          placeholder="e.g. target_validation, mechanism_of_action"
          {...register('claim_type', { required: true })}
        />
      </div>
      <Button type="submit" disabled={formState.isSubmitting}>
        Create hypothesis
      </Button>
    </form>
  );
}
