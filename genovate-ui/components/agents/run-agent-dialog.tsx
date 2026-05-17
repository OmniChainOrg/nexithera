'use client';

import { useState } from 'react';
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { useRunAgent } from '@/lib/hooks/use-agent-runs';
import type { AgentName } from '@/lib/types/genovate';

const AGENTS: { name: AgentName; description: string }[] = [
  { name: 'TargetBiology', description: 'Mechanistic target biology and pathway reasoning.' },
  { name: 'Oncology', description: 'Oncology-specific therapeutic context.' },
  { name: 'EvidenceSynthesizer', description: 'Synthesizes literature into structured claims.' },
  { name: 'SimulationCritic', description: 'Reviews simulation outputs and suggests next steps.' },
];

export function RunAgentDialog({ programId }: { programId: string }) {
  const [open, setOpen] = useState(false);
  const [agent, setAgent] = useState<AgentName>('TargetBiology');
  const [runType, setRunType] = useState<string>('target_evaluation');
  const [inputsText, setInputsText] = useState<string>('{}');
  const runAgent = useRunAgent();

  const submit = async () => {
    let inputs: Record<string, unknown> = {};
    try {
      inputs = JSON.parse(inputsText || '{}');
    } catch {
      inputs = { raw: inputsText };
    }
    await runAgent.mutateAsync({ agent_name: agent, run_type: runType, program_id: programId, inputs });
    setOpen(false);
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>Run agent</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Run an agent</DialogTitle>
          <DialogDescription>
            Trigger one of the Genovate scientific agents against this program.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div>
            <label className="text-sm font-medium">Agent</label>
            <Select value={agent} onValueChange={(v) => setAgent(v as AgentName)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {AGENTS.map((a) => (
                  <SelectItem key={a.name} value={a.name}>
                    {a.name} — {a.description}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="text-sm font-medium" htmlFor="run-type">
              Run type
            </label>
            <input
              id="run-type"
              className="mt-1 flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={runType}
              onChange={(e) => setRunType(e.target.value)}
            />
          </div>
          <div>
            <label className="text-sm font-medium" htmlFor="inputs">
              Inputs (JSON)
            </label>
            <Textarea
              id="inputs"
              rows={4}
              value={inputsText}
              onChange={(e) => setInputsText(e.target.value)}
            />
          </div>
        </div>
        <DialogFooter>
          <Button onClick={submit} disabled={runAgent.isPending}>
            {runAgent.isPending ? 'Submitting…' : 'Run'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
