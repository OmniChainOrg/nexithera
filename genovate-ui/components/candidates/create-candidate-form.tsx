'use client';

import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useCreateCandidate } from '@/lib/hooks/use-candidates';
import type { CandidateType } from '@/lib/types/genovate';

const candidateTypes: CandidateType[] = [
  'small_molecule',
  'biologic',
  'immunotherapy',
  'formulation',
  'gene_target',
  'protein_target',
];

const schema = z.object({
  name: z.string().min(2),
  candidate_type: z.enum(candidateTypes as [CandidateType, ...CandidateType[]]),
  therapeutic_area: z.string().min(2),
  mechanism_of_action: z.string().optional(),
});

export function CreateCandidateForm({ programId }: { programId: string }) {
  const create = useCreateCandidate(programId);
  const { register, handleSubmit, setValue, reset, formState, watch } =
    useForm<z.infer<typeof schema>>();

  const onSubmit = handleSubmit(async (values) => {
    const parsed = schema.safeParse(values);
    if (!parsed.success) return;
    await create.mutateAsync({ program_id: programId, ...parsed.data });
    reset();
  });

  const candidateType = watch('candidate_type');

  return (
    <form onSubmit={onSubmit} className="space-y-3">
      <div>
        <label className="text-sm font-medium" htmlFor="name">
          Candidate name
        </label>
        <Input id="name" {...register('name', { required: true })} />
      </div>
      <div>
        <label className="text-sm font-medium">Type</label>
        <Select
          value={candidateType}
          onValueChange={(v) => setValue('candidate_type', v as CandidateType)}
        >
          <SelectTrigger>
            <SelectValue placeholder="Select a type" />
          </SelectTrigger>
          <SelectContent>
            {candidateTypes.map((t) => (
              <SelectItem key={t} value={t}>
                {t}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div>
        <label className="text-sm font-medium" htmlFor="therapeutic_area">
          Therapeutic area
        </label>
        <Input id="therapeutic_area" {...register('therapeutic_area', { required: true })} />
      </div>
      <div>
        <label className="text-sm font-medium" htmlFor="mechanism_of_action">
          Mechanism of action
        </label>
        <Input id="mechanism_of_action" {...register('mechanism_of_action')} />
      </div>
      <Button type="submit" disabled={formState.isSubmitting || create.isPending}>
        {create.isPending ? 'Creating…' : 'Create candidate'}
      </Button>
    </form>
  );
}
