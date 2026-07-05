'use client';

import { useState, useMemo } from 'react';
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
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { useRunAgent } from '@/lib/hooks/use-agent-runs';
import toast from 'react-hot-toast';

interface InputField {
  key: string;
  label: string;
  type: 'text' | 'number' | 'select' | 'json';
  required?: boolean;
  placeholder?: string;
  options?: string[];
  default?: string;
}

interface AgentConfig {
  name: string;
  backendName: string;
  description: string;
  runType: string;
  inputFields: InputField[];
}

const AGENTS: AgentConfig[] = [
  {
    name: 'Target Biology Agent',
    backendName: 'Target Biology Agent',
    description: 'Evaluates target relevance, pathway plausibility, and disease fit.',
    runType: 'target_assessment',
    inputFields: [
      { key: 'target_name', label: 'Target name', type: 'text', required: true, placeholder: 'e.g. EGFR' },
      { key: 'disease_name', label: 'Disease name', type: 'text', required: true, placeholder: 'e.g. Non-small cell lung cancer' },
      { key: 'target_type', label: 'Target type', type: 'select', options: ['gene', 'protein', 'pathway', 'compound'], default: 'gene' },
    ],
  },
  {
    name: 'Oncology & Immunotherapy Agent',
    backendName: 'Oncology & Immunotherapy Agent',
    description: 'Oncology-specific therapeutic context, TME, and immunotherapy landscape.',
    runType: 'target_assessment',
    inputFields: [
      { key: 'target_name', label: 'Target name', type: 'text', required: true },
      { key: 'tumor_type', label: 'Tumor type', type: 'text', required: true, placeholder: 'e.g. NSCLC, solid_tumor' },
      { key: 'biomarker', label: 'Biomarker (optional)', type: 'text', required: false },
    ],
  },
  {
    name: 'Evidence Synthesizer Agent',
    backendName: 'Evidence Synthesizer Agent',
    description: 'Synthesizes multi-source literature into structured evidence claims.',
    runType: 'evidence_synthesis',
    inputFields: [
      { key: 'candidate_name', label: 'Candidate / target name', type: 'text', required: true },
      { key: 'synthesis_focus', label: 'Synthesis focus', type: 'text', placeholder: 'e.g. safety, efficacy, mechanism' },
    ],
  },
  {
    name: 'Simulation Critic Agent',
    backendName: 'Simulation Critic Agent',
    description: 'Reviews simulation plans and outputs; suggests improvements.',
    runType: 'simulation_critique',
    inputFields: [
      { key: 'target_name', label: 'Target name', type: 'text', required: true },
      { key: 'simulation_plan', label: 'Simulation plan (JSON)', type: 'json', required: true, placeholder: '{"zone_type": "pkpd", "replicates": 3}' },
    ],
  },
  {
    name: 'Target Discovery Agent',
    backendName: 'Target Discovery Agent',
    description: 'Discovers novel, under-supported targets with proposed hypotheses.',
    runType: 'target_assessment',
    inputFields: [
      { key: 'disease_name', label: 'Disease name', type: 'text', placeholder: 'e.g. Pancreatic adenocarcinoma' },
      { key: 'top_k', label: 'Number of targets', type: 'number', default: '10' },
    ],
  },
  {
    name: 'Gap Analysis Agent',
    backendName: 'Gap Analysis Agent',
    description: 'Identifies evidence gaps and proposes experiments to fill them.',
    runType: 'gap_analysis',
    inputFields: [
      { key: 'focus_area', label: 'Focus area (optional)', type: 'text', placeholder: 'e.g. safety, MOA, biomarkers' },
    ],
  },
  {
    name: 'Active Learning Agent',
    backendName: 'Active Learning Agent',
    description: 'Proposes next best experiments ranked by information gain.',
    runType: 'active_learning',
    inputFields: [
      { key: 'max_experiments', label: 'Max experiments', type: 'number', default: '5' },
    ],
  },
  {
    name: 'Safety & Toxicity Agent',
    backendName: 'Safety & Toxicity Agent',
    description: 'Flags potential safety and toxicity concerns early.',
    runType: 'safety_assessment',
    inputFields: [
      { key: 'candidate_name', label: 'Candidate name', type: 'text', required: true },
      { key: 'mechanism', label: 'Mechanism of action', type: 'text' },
    ],
  },
  {
    name: 'Competitive Landscape Agent',
    backendName: 'Competitive Landscape Agent',
    description: 'Maps the competitive landscape for a target/indication.',
    runType: 'competitive_analysis',
    inputFields: [
      { key: 'target_name', label: 'Target name', type: 'text', required: true },
      { key: 'indication', label: 'Indication', type: 'text', required: true },
    ],
  },
  {
    name: 'Clinical Forecaster Agent',
    backendName: 'Clinical Forecaster Agent',
    description: 'Forecasts clinical trial success probability.',
    runType: 'clinical_forecast',
    inputFields: [
      { key: 'candidate_name', label: 'Candidate name', type: 'text', required: true },
      { key: 'phase', label: 'Trial phase', type: 'select', options: ['Phase 1', 'Phase 2', 'Phase 3'], required: true },
    ],
  },
  {
    name: 'Trial Design Agent',
    backendName: 'Trial Design Agent',
    description: 'Proposes optimal trial design with endpoints and enrollment strategy.',
    runType: 'trial_design',
    inputFields: [
      { key: 'indication', label: 'Indication', type: 'text', required: true },
      { key: 'phase', label: 'Phase', type: 'select', options: ['Phase 1', 'Phase 2', 'Phase 3'] },
    ],
  },
  {
    name: 'IP Position Agent',
    backendName: 'IP Position Agent',
    description: 'Assesses freedom-to-operate and IP landscape.',
    runType: 'ip_assessment',
    inputFields: [
      { key: 'candidate_name', label: 'Candidate name', type: 'text', required: true },
      { key: 'target_name', label: 'Target name', type: 'text' },
    ],
  },
  {
    name: 'Historical Precedent Agent',
    backendName: 'Historical Precedent Agent',
    description: 'Finds similar historical programs and extracts lessons.',
    runType: 'precedent_analysis',
    inputFields: [
      { key: 'modality', label: 'Modality', type: 'text', placeholder: 'e.g. small molecule, biologic' },
      { key: 'target_name', label: 'Target name', type: 'text' },
    ],
  },
  {
    name: 'IND Readiness Agent',
    backendName: 'IND Readiness Agent',
    description: 'Evaluates IND readiness checklist and gaps.',
    runType: 'ind_readiness',
    inputFields: [
      { key: 'candidate_name', label: 'Candidate name', type: 'text', required: true },
    ],
  },
];

function buildInitialValues(fields: InputField[]): Record<string, string> {
  const vals: Record<string, string> = {};
  for (const f of fields) {
    vals[f.key] = f.default ?? '';
  }
  return vals;
}

export function RunAgentDialog({ programId }: { programId: string }) {
  const [open, setOpen] = useState(false);
  const [selectedAgentName, setSelectedAgentName] = useState<string>(AGENTS[0].name);
  const [fieldValues, setFieldValues] = useState<Record<string, string>>(
    buildInitialValues(AGENTS[0].inputFields)
  );
  const runAgent = useRunAgent();

  const selectedAgent = useMemo(
    () => AGENTS.find((a) => a.name === selectedAgentName) ?? AGENTS[0],
    [selectedAgentName]
  );

  const handleAgentChange = (name: string) => {
    const agent = AGENTS.find((a) => a.name === name) ?? AGENTS[0];
    setSelectedAgentName(name);
    setFieldValues(buildInitialValues(agent.inputFields));
  };

  const setField = (key: string, value: string) => {
    setFieldValues((prev) => ({ ...prev, [key]: value }));
  };

  const buildInputs = (): Record<string, unknown> => {
    const inputs: Record<string, unknown> = {};
    for (const field of selectedAgent.inputFields) {
      const raw = fieldValues[field.key] ?? '';
      if (!raw && !field.required) continue;
      if (field.type === 'json') {
        try {
          inputs[field.key] = JSON.parse(raw || '{}');
        } catch {
          inputs[field.key] = raw;
        }
      } else if (field.type === 'number') {
        inputs[field.key] = raw !== '' ? Number(raw) : undefined;
      } else {
        inputs[field.key] = raw;
      }
    }
    return inputs;
  };

  const submit = async () => {
    const inputs = buildInputs();
    try {
      await runAgent.mutateAsync({
        agent_name: selectedAgent.backendName,
        run_type: selectedAgent.runType,
        program_id: programId,
        inputs,
      });
      toast.success(`${selectedAgent.name} run started`);
      setOpen(false);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      toast.error(`Failed to start agent run: ${message}`);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>Run agent</Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Run an agent</DialogTitle>
          <DialogDescription>
            {selectedAgent.description}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <label className="text-sm font-medium">Agent</label>
            <Select value={selectedAgentName} onValueChange={handleAgentChange}>
              <SelectTrigger className="mt-1">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {AGENTS.map((a) => (
                  <SelectItem key={a.name} value={a.name}>
                    {a.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {selectedAgent.inputFields.map((field) => (
            <div key={field.key}>
              <label className="text-sm font-medium">
                {field.label}
                {field.required && <span className="ml-1 text-destructive">*</span>}
              </label>
              {field.type === 'select' ? (
                <Select
                  value={fieldValues[field.key] ?? field.default ?? ''}
                  onValueChange={(v) => setField(field.key, v)}
                >
                  <SelectTrigger className="mt-1">
                    <SelectValue placeholder="Select…" />
                  </SelectTrigger>
                  <SelectContent>
                    {(field.options ?? []).map((opt) => (
                      <SelectItem key={opt} value={opt}>
                        {opt}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ) : field.type === 'json' ? (
                <Textarea
                  className="mt-1 font-mono text-xs"
                  rows={4}
                  placeholder={field.placeholder ?? '{}'}
                  value={fieldValues[field.key] ?? ''}
                  onChange={(e) => setField(field.key, e.target.value)}
                />
              ) : (
                <Input
                  className="mt-1"
                  type={field.type === 'number' ? 'number' : 'text'}
                  placeholder={field.placeholder}
                  value={fieldValues[field.key] ?? ''}
                  onChange={(e) => setField(field.key, e.target.value)}
                />
              )}
            </div>
          ))}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={runAgent.isPending}>
            {runAgent.isPending ? `Running ${selectedAgent.name}…` : 'Run →'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
