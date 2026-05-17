'use client';

import { useEffect } from 'react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { usePrograms } from '@/lib/hooks/use-programs';
import { useProgramStore } from '@/lib/stores/program-store';

export function ProgramSelector() {
  const { data: programs, isLoading, isError } = usePrograms();
  const currentProgramId = useProgramStore((s) => s.currentProgramId);
  const setCurrentProgramId = useProgramStore((s) => s.setCurrentProgramId);

  // Auto-select the first program when none is selected yet.
  useEffect(() => {
    if (!currentProgramId && programs && programs.length > 0) {
      setCurrentProgramId(programs[0].id);
    }
  }, [currentProgramId, programs, setCurrentProgramId]);

  if (isError) {
    return (
      <span className="text-sm text-destructive" role="alert">
        Could not load programs
      </span>
    );
  }

  return (
    <Select
      value={currentProgramId ?? undefined}
      onValueChange={(v) => setCurrentProgramId(v)}
      disabled={isLoading || !programs?.length}
    >
      <SelectTrigger className="w-[260px]" aria-label="Select active program">
        <SelectValue placeholder={isLoading ? 'Loading programs…' : 'Select a program'} />
      </SelectTrigger>
      <SelectContent>
        {programs?.map((p) => (
          <SelectItem key={p.id} value={p.id}>
            {p.name}{' '}
            <span className="ml-1 text-xs text-muted-foreground">· {p.therapeutic_area}</span>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
