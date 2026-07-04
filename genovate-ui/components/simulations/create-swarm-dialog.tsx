'use client';

import { useState, useEffect, useCallback } from 'react';
import { useForm, Controller } from 'react-hook-form';
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ChevronDown, ChevronRight, Settings2, Copy } from 'lucide-react';
import { useCreateSwarm, useZones, useCXUs } from '@/lib/hooks/use-simulations';

const SWARM_TYPES = ['cooperative', 'competitive', 'ensemble', 'adversarial'] as const;

const ZONE_DOMAINS = [
  'biotech', 'healthcare', 'pharma', 'genomics',
  'immunology', 'oncology', 'neuroscience', 'rare_disease',
] as const;

const AGENT_PROFILES = ['exploratory', 'diagnostic', 'generative', 'adversarial', 'consensus'] as const;
const AUTO_SIM_FREQUENCIES = ['manual', 'hourly', 'daily', 'weekly', 'on_data_change'] as const;
const IMPACT_DOMAINS = [
  'local_policy', 'global_policy', 'candidate_scoring',
  'hypothesis_validation', 'evidence_gap',
] as const;
const CONFIDENTIALITIES = ['public', 'private', 'dao_shared', 'guardian_only'] as const;
const EPISTEMIC_INTENTS = ['diagnostic', 'generative', 'falsification', 'synthesis', 'active_learning'] as const;
const ETHICAL_SENSITIVITIES = [
  'low_sensitivity_stable', 'medium_sensitivity', 'high_sensitivity', 'critical',
] as const;
const AGGREGATION_METHODS = ['consensus', 'weighted_average', 'best_of', 'voting', 'meta_learner'] as const;
const CXU_ROLES = ['worker', 'leader', 'critic', 'arbiter'] as const;

interface FormValues {
  name: string;
  objective: string;
  zone_domain: string;
  recursion_level: string;
  simulation_agent_profile: string;
  auto_simulation_frequency: string;
  impact_domain: string;
  confidentiality: string;
  epistemic_intent: string;
  ethical_sensitivity: string;
  guardian_id: string;
  drift_threshold: string;
  require_guardian_approval: boolean;
  escalation_threshold: string;
  shared_with_dao: boolean;
  audit_trail: boolean;
  verifiable_hash: boolean;
  aggregation_method: string;
}

const DRAFT_KEY = (id: string) => `genovate:draft:swarm:${id}`;

function stripEmpty(obj: Record<string, unknown>): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(obj)) {
    if (v === undefined || v === null || v === '') continue;
    if (typeof v === 'object' && !Array.isArray(v)) {
      const nested = stripEmpty(v as Record<string, unknown>);
      if (Object.keys(nested).length > 0) result[k] = nested;
    } else {
      result[k] = v;
    }
  }
  return result;
}

export function CreateSwarmDialog({ programId }: { programId: string }) {
  const [open, setOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('configure');
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [swarmType, setSwarmType] = useState('');
  const [selectedCXUs, setSelectedCXUs] = useState<string[]>([]);
  const [matrixPairs, setMatrixPairs] = useState<Array<{ zoneId: string; cxuId: string }>>([]);
  const [cxuRoles, setCxuRoles] = useState<Record<string, string>>({});
  const [cxuWeights, setCxuWeights] = useState<Record<string, string>>({});

  const { register, handleSubmit, reset, watch, control, setValue } = useForm<FormValues>({
    defaultValues: {
      name: '', objective: '',
      zone_domain: '', recursion_level: '', simulation_agent_profile: '',
      auto_simulation_frequency: '', impact_domain: '', confidentiality: '',
      epistemic_intent: '', ethical_sensitivity: '', guardian_id: '', drift_threshold: '',
      require_guardian_approval: false, escalation_threshold: '',
      shared_with_dao: false, audit_trail: true, verifiable_hash: true,
      aggregation_method: '',
    },
  });

  const createSwarm = useCreateSwarm(programId);
  const zones = useZones(programId);
  const cxus = useCXUs(programId);

  const values = watch();

  const buildConfig = useCallback(
    (v: FormValues, cxuIds: string[], pairs: typeof matrixPairs, roles: typeof cxuRoles, weights: typeof cxuWeights) => {
      const members = cxuIds.map((id) => ({
        cxu_id: id,
        role: roles[id] ?? 'worker',
        weight: weights[id] ? Number(weights[id]) : undefined,
      }));
      return stripEmpty({
        zone_domain: v.zone_domain,
        recursion_level: v.recursion_level ? Number(v.recursion_level) : '',
        simulation_agent_profile: v.simulation_agent_profile,
        auto_simulation_frequency: v.auto_simulation_frequency,
        impact_domain: v.impact_domain,
        confidentiality: v.confidentiality,
        epistemic_intent: v.epistemic_intent,
        ethical_sensitivity: v.ethical_sensitivity,
        guardian_id: v.guardian_id,
        drift_threshold: v.drift_threshold ? Number(v.drift_threshold) : '',
        members: members.length ? members : '',
        guardian_gating: {
          require_approval: v.require_guardian_approval || '',
          escalation_threshold: v.escalation_threshold ? Number(v.escalation_threshold) : '',
        },
        provenance: {
          shared_with_dao: v.shared_with_dao || '',
          audit_trail: v.audit_trail,
          verifiable_hash: v.verifiable_hash,
        },
        aggregation_method: v.aggregation_method,
        variations: pairs.length ? pairs : '',
      });
    },
    [],
  );

  useEffect(() => {
    if (!open) return;
    try {
      const raw = localStorage.getItem(DRAFT_KEY(programId));
      if (!raw) return;
      const draft = JSON.parse(raw);
      if (draft.formValues) {
        (Object.keys(draft.formValues) as Array<keyof FormValues>).forEach((k) =>
          setValue(k, draft.formValues[k]),
        );
      }
      if (draft.swarmType) setSwarmType(draft.swarmType);
      if (draft.selectedCXUs) setSelectedCXUs(draft.selectedCXUs);
    } catch {
      // ignore malformed draft
    }
  }, [open, programId, setValue]);

  const handleClose = useCallback(() => {
    reset();
    setSwarmType('');
    setSelectedCXUs([]);
    setMatrixPairs([]);
    setCxuRoles({});
    setCxuWeights({});
    setActiveTab('configure');
    setAdvancedOpen(false);
    setOpen(false);
  }, [reset]);

  const saveDraft = useCallback(() => {
    localStorage.setItem(
      DRAFT_KEY(programId),
      JSON.stringify({ formValues: values, swarmType, selectedCXUs }),
    );
    toast.success('Draft saved');
  }, [programId, values, swarmType, selectedCXUs]);

  const toggleCXU = (id: string) =>
    setSelectedCXUs((prev) => (prev.includes(id) ? prev.filter((c) => c !== id) : [...prev, id]));

  const onRunNow = handleSubmit(async (v) => {
    if (!swarmType) { toast.error('Swarm type is required'); return; }
    const advConfig = buildConfig(v, selectedCXUs, matrixPairs, cxuRoles, cxuWeights);
    await createSwarm.mutateAsync(
      {
        program_id: programId,
        objective: v.objective,
        swarm_config: {
          name: v.name,
          swarm_type: swarmType,
          cxu_ids: selectedCXUs,
          ...advConfig,
        },
      },
      {
        onSuccess: () => {
          toast.success('Swarm created');
          localStorage.removeItem(DRAFT_KEY(programId));
          handleClose();
        },
        onError: (err) => toast.error(err instanceof Error ? err.message : 'Failed to create swarm'),
      },
    );
  });

  const togglePair = (zId: string, cId: string) =>
    setMatrixPairs((prev) =>
      prev.some((p) => p.zoneId === zId && p.cxuId === cId)
        ? prev.filter((p) => !(p.zoneId === zId && p.cxuId === cId))
        : [...prev, { zoneId: zId, cxuId: cId }],
    );

  const configJson = JSON.stringify(
    {
      swarm_type: swarmType || undefined,
      name: values.name || undefined,
      objective: values.objective || undefined,
      cxu_ids: selectedCXUs.length ? selectedCXUs : undefined,
      ...buildConfig(values, selectedCXUs, matrixPairs, cxuRoles, cxuWeights),
    },
    null, 2,
  );

  const zoneList = zones.data ?? [];
  const cxuList = cxus.data ?? [];

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) handleClose(); else setOpen(true); }}>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline">Create Swarm</Button>
      </DialogTrigger>
      <DialogContent
        className={
          activeTab === 'expert'
            ? 'sm:max-w-3xl max-h-[90vh] overflow-y-auto'
            : 'sm:max-w-lg max-h-[90vh] overflow-y-auto'
        }
      >
        <DialogHeader>
          <DialogTitle>New Swarm</DialogTitle>
          <DialogDescription>Create a multi-agent CXU swarm for coordinated simulation.</DialogDescription>
        </DialogHeader>

        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="w-full">
            <TabsTrigger value="configure" className="flex-1">Configure</TabsTrigger>
            <TabsTrigger value="expert" className="flex-1 gap-1">
              <Settings2 className="h-3.5 w-3.5" />
              Expert
              <span className="ml-1 rounded bg-muted px-1 py-0.5 text-[10px] font-normal opacity-70">
                SirrenaSim™
              </span>
            </TabsTrigger>
          </TabsList>

          {/* ── Configure tab ── */}
          <TabsContent value="configure" className="space-y-3 mt-2">
            <div>
              <label className="text-sm font-medium" htmlFor="sw-name">
                Name <span className="text-destructive">*</span>
              </label>
              <Input id="sw-name" {...register('name', { required: true })} placeholder="e.g. Swarm-01" />
            </div>
            <div>
              <label className="text-sm font-medium">
                Swarm type <span className="text-destructive">*</span>
              </label>
              <Select value={swarmType} onValueChange={setSwarmType}>
                <SelectTrigger><SelectValue placeholder="Select swarm type" /></SelectTrigger>
                <SelectContent>
                  {SWARM_TYPES.map((t) => (
                    <SelectItem key={t} value={t}>{t}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-sm font-medium" htmlFor="sw-obj">
                Objective <span className="text-destructive">*</span>
              </label>
              <Textarea
                id="sw-obj" rows={2}
                {...register('objective', { required: true })}
                placeholder="Describe the swarm objective…"
              />
            </div>
            <div>
              <label className="text-sm font-medium">CXU selection</label>
              {cxuList.length ? (
                <div className="mt-1 max-h-36 overflow-auto rounded-md border p-2 space-y-1">
                  {cxuList.map((c) => (
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

            {/* Advanced collapsible */}
            <div className="rounded-md border">
              <button
                type="button"
                onClick={() => setAdvancedOpen((s) => !s)}
                className="flex w-full items-center gap-2 px-3 py-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
              >
                {advancedOpen
                  ? <ChevronDown className="h-4 w-4" />
                  : <ChevronRight className="h-4 w-4" />}
                Advanced EpistemicOS Parameters
              </button>
              {advancedOpen && (
                <div className="border-t px-3 pb-3 pt-2 space-y-3">
                  <p className="text-xs italic text-muted-foreground">
                    These parameters are passed directly to EpistemicOS.
                  </p>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-sm font-medium">Zone Domain</label>
                      <Controller
                        name="zone_domain" control={control}
                        render={({ field }) => (
                          <Select value={field.value} onValueChange={field.onChange}>
                            <SelectTrigger><SelectValue placeholder="Select…" /></SelectTrigger>
                            <SelectContent>
                              {ZONE_DOMAINS.map((d) => (
                                <SelectItem key={d} value={d}>{d.replace(/_/g, ' ')}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        )}
                      />
                    </div>
                    <div>
                      <label className="text-sm font-medium">Recursion Level</label>
                      <Input type="number" min={1} max={5} placeholder="1–5" {...register('recursion_level')} />
                    </div>
                    <div>
                      <label className="text-sm font-medium">Agent Profile</label>
                      <Controller
                        name="simulation_agent_profile" control={control}
                        render={({ field }) => (
                          <Select value={field.value} onValueChange={field.onChange}>
                            <SelectTrigger><SelectValue placeholder="Select…" /></SelectTrigger>
                            <SelectContent>
                              {AGENT_PROFILES.map((p) => (
                                <SelectItem key={p} value={p}>{p}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        )}
                      />
                    </div>
                    <div>
                      <label className="text-sm font-medium">Auto Sim Frequency</label>
                      <Controller
                        name="auto_simulation_frequency" control={control}
                        render={({ field }) => (
                          <Select value={field.value} onValueChange={field.onChange}>
                            <SelectTrigger><SelectValue placeholder="Select…" /></SelectTrigger>
                            <SelectContent>
                              {AUTO_SIM_FREQUENCIES.map((f) => (
                                <SelectItem key={f} value={f}>{f.replace(/_/g, ' ')}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        )}
                      />
                    </div>
                    <div>
                      <label className="text-sm font-medium">Impact Domain</label>
                      <Controller
                        name="impact_domain" control={control}
                        render={({ field }) => (
                          <Select value={field.value} onValueChange={field.onChange}>
                            <SelectTrigger><SelectValue placeholder="Select…" /></SelectTrigger>
                            <SelectContent>
                              {IMPACT_DOMAINS.map((d) => (
                                <SelectItem key={d} value={d}>{d.replace(/_/g, ' ')}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        )}
                      />
                    </div>
                    <div>
                      <label className="text-sm font-medium">Confidentiality</label>
                      <Controller
                        name="confidentiality" control={control}
                        render={({ field }) => (
                          <Select value={field.value} onValueChange={field.onChange}>
                            <SelectTrigger><SelectValue placeholder="Select…" /></SelectTrigger>
                            <SelectContent>
                              {CONFIDENTIALITIES.map((c) => (
                                <SelectItem key={c} value={c}>{c.replace(/_/g, ' ')}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        )}
                      />
                    </div>
                    <div>
                      <label className="text-sm font-medium">Epistemic Intent</label>
                      <Controller
                        name="epistemic_intent" control={control}
                        render={({ field }) => (
                          <Select value={field.value} onValueChange={field.onChange}>
                            <SelectTrigger><SelectValue placeholder="Select…" /></SelectTrigger>
                            <SelectContent>
                              {EPISTEMIC_INTENTS.map((i) => (
                                <SelectItem key={i} value={i}>{i.replace(/_/g, ' ')}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        )}
                      />
                    </div>
                    <div>
                      <label className="text-sm font-medium">Ethical Sensitivity</label>
                      <Controller
                        name="ethical_sensitivity" control={control}
                        render={({ field }) => (
                          <Select value={field.value} onValueChange={field.onChange}>
                            <SelectTrigger><SelectValue placeholder="Select…" /></SelectTrigger>
                            <SelectContent>
                              {ETHICAL_SENSITIVITIES.map((s) => (
                                <SelectItem key={s} value={s}>{s.replace(/_/g, ' ')}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        )}
                      />
                    </div>
                  </div>
                  <div>
                    <label className="text-sm font-medium" htmlFor="sw-guardian">Guardian ID</label>
                    <Input id="sw-guardian" {...register('guardian_id')} placeholder="UUID or guardian name" />
                  </div>
                  <div>
                    <label className="text-sm font-medium" htmlFor="sw-drift">Drift Threshold (0–1)</label>
                    <Input
                      id="sw-drift" type="number" min={0} max={1} step={0.01}
                      placeholder="e.g. 0.25"
                      {...register('drift_threshold')}
                    />
                  </div>
                </div>
              )}
            </div>
          </TabsContent>

          {/* ── Expert tab ── */}
          <TabsContent value="expert" className="space-y-4 mt-2">
            <div className="rounded-md border border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/30 px-3 py-2 text-xs text-amber-800 dark:text-amber-300 italic">
              EpistemicOS executes all simulation work. Genovate orchestrates and stores the resulting metadata.
            </div>

            {/* Zone × CXU Matrix */}
            <div>
              <h4 className="text-sm font-semibold mb-2">Zone × CXU Matrix</h4>
              {zoneList.length && cxuList.length ? (
                <div className="overflow-auto rounded-md border">
                  <table className="min-w-full text-xs">
                    <thead>
                      <tr className="bg-muted/50">
                        <th className="px-2 py-1.5 text-left font-medium">Zone \ CXU</th>
                        {cxuList.map((c) => (
                          <th key={c.id} className="px-2 py-1.5 text-center font-medium max-w-[80px] truncate">
                            {c.name}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {zoneList.map((z) => (
                        <tr key={z.id} className="border-t">
                          <td className="px-2 py-1.5 font-medium max-w-[100px] truncate">{z.name}</td>
                          {cxuList.map((c) => (
                            <td key={c.id} className="px-2 py-1.5 text-center">
                              <input
                                type="checkbox"
                                className="accent-primary"
                                checked={matrixPairs.some((p) => p.zoneId === z.id && p.cxuId === c.id)}
                                onChange={() => togglePair(z.id, c.id)}
                              />
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-xs text-muted-foreground">
                  {!zoneList.length && !cxuList.length
                    ? 'No zones or CXUs available yet.'
                    : !zoneList.length ? 'No zones available yet.'
                    : 'No CXUs available yet.'}
                </p>
              )}
            </div>

            {/* Swarm Configuration — member roles & weights */}
            {selectedCXUs.length > 0 && (
              <div>
                <h4 className="text-sm font-semibold mb-2">Member Roles & Weights</h4>
                <div className="space-y-2">
                  {selectedCXUs.map((cxuId) => {
                    const cxu = cxuList.find((c) => c.id === cxuId);
                    return (
                      <div key={cxuId} className="flex items-center gap-3">
                        <span className="w-28 truncate text-xs font-medium">{cxu?.name ?? cxuId}</span>
                        <Select
                          value={cxuRoles[cxuId] ?? 'worker'}
                          onValueChange={(v) => setCxuRoles((prev) => ({ ...prev, [cxuId]: v }))}
                        >
                          <SelectTrigger className="h-7 w-28 text-xs"><SelectValue /></SelectTrigger>
                          <SelectContent>
                            {CXU_ROLES.map((r) => (
                              <SelectItem key={r} value={r}>{r}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <Input
                          type="number" min={0} max={2} step={0.1}
                          placeholder="weight (0–2)"
                          className="h-7 w-28 text-xs"
                          value={cxuWeights[cxuId] ?? ''}
                          onChange={(e) =>
                            setCxuWeights((prev) => ({ ...prev, [cxuId]: e.target.value }))
                          }
                        />
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Aggregation Method */}
            <div>
              <label className="text-sm font-medium">Aggregation Method</label>
              <Controller
                name="aggregation_method" control={control}
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger><SelectValue placeholder="Select…" /></SelectTrigger>
                    <SelectContent>
                      {AGGREGATION_METHODS.map((m) => (
                        <SelectItem key={m} value={m}>{m.replace(/_/g, ' ')}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </div>

            {/* Guardian Gating */}
            <div>
              <h4 className="text-sm font-semibold mb-2">Guardian Gating</h4>
              <div className="space-y-2">
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input type="checkbox" className="accent-primary" {...register('require_guardian_approval')} />
                  Require Guardian approval before run executes
                </label>
                <div>
                  <label className="text-sm font-medium" htmlFor="sw-esc">Escalation Threshold (0–1)</label>
                  <Input
                    id="sw-esc" type="number" min={0} max={1} step={0.01}
                    placeholder="e.g. 0.8"
                    {...register('escalation_threshold')}
                  />
                </div>
              </div>
            </div>

            {/* Provenance */}
            <div>
              <h4 className="text-sm font-semibold mb-2">Provenance Config</h4>
              <div className="space-y-1.5">
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input type="checkbox" className="accent-primary" {...register('shared_with_dao')} />
                  Shared with DAO
                </label>
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input type="checkbox" className="accent-primary" {...register('audit_trail')} />
                  Audit trail
                </label>
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input type="checkbox" className="accent-primary" {...register('verifiable_hash')} />
                  Verifiable hash
                </label>
              </div>
            </div>

            {/* Raw Config Preview */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <h4 className="text-sm font-semibold">Raw EpistemicOS Config Preview</h4>
                <Button
                  type="button" size="sm" variant="ghost"
                  className="h-7 gap-1 text-xs"
                  onClick={() => { navigator.clipboard.writeText(configJson); toast.success('Copied!'); }}
                >
                  <Copy className="h-3.5 w-3.5" /> Copy JSON
                </Button>
              </div>
              <pre className="overflow-auto rounded-md bg-muted p-3 text-xs leading-relaxed max-h-52">
                {configJson}
              </pre>
            </div>
          </TabsContent>
        </Tabs>

        <DialogFooter className="gap-2 pt-2">
          <Button type="button" variant="ghost" onClick={handleClose}>Cancel</Button>
          <Button type="button" variant="outline" onClick={saveDraft}>Save Draft</Button>
          <Button
            type="button"
            onClick={onRunNow}
            disabled={!swarmType || createSwarm.isPending}
          >
            {createSwarm.isPending ? 'Creating…' : 'Run Now →'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
