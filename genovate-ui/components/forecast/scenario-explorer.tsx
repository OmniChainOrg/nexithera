'use client';

import { useEffect, useMemo, useState } from 'react';
import { Copy, RotateCcw, Save } from 'lucide-react';
import toast from 'react-hot-toast';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Slider } from '@/components/ui/slider';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import type { SavedScenario, TrialDesign } from '@/lib/api/forecast';
import { encodeTrialDesign } from '@/lib/utils/clinical-forecast';

interface ScenarioExplorerProps {
  baseTrialDesign: TrialDesign;
  trialDesign: TrialDesign;
  onChange: (next: TrialDesign) => void;
  onReset: () => void;
  endpointOptions?: { value: string; label: string }[];
  savedScenarios?: SavedScenario[];
  onSaveScenario?: (name: string, design: TrialDesign) => Promise<void> | void;
  onLoadScenario?: (scenario: SavedScenario) => void;
  isRecalculating?: boolean;
  focusedFactor?: string | null;
}

const ALPHA_OPTIONS = ['0.01', '0.05', '0.10'];

/**
 * Interactive sliders that mutate a {@link TrialDesign} object. The parent
 * is responsible for debouncing the resulting changes before re-calling
 * `POST /forecast/clinical` (see `useDebouncedValue`).
 */
export function ScenarioExplorer({
  baseTrialDesign,
  trialDesign,
  onChange,
  onReset,
  endpointOptions = [],
  savedScenarios = [],
  onSaveScenario,
  onLoadScenario,
  isRecalculating = false,
  focusedFactor = null,
}: ScenarioExplorerProps) {
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [saveOpen, setSaveOpen] = useState(false);
  const [scenarioName, setScenarioName] = useState('');

  const patch = (delta: Partial<TrialDesign>) =>
    onChange({ ...trialDesign, ...delta });

  const enrollment = trialDesign.enrollment ?? baseTrialDesign.enrollment ?? 120;
  const power = trialDesign.statistical_power ?? baseTrialDesign.statistical_power ?? 0.8;
  const duration = trialDesign.duration_months ?? baseTrialDesign.duration_months ?? 12;
  const alpha = (trialDesign.alpha ?? baseTrialDesign.alpha ?? 0.05).toString();
  const enrichment = trialDesign.patient_enrichment ?? false;

  // Highlight the focused factor for ~2s for user feedback.
  const [highlight, setHighlight] = useState<string | null>(null);
  useEffect(() => {
    if (!focusedFactor) return;
    setHighlight(focusedFactor);
    const t = setTimeout(() => setHighlight(null), 2000);
    return () => clearTimeout(t);
  }, [focusedFactor]);

  const highlightClass = (factor: string) =>
    highlight === factor
      ? 'ring-2 ring-primary ring-offset-2 ring-offset-background rounded-md'
      : '';

  const shareLink = useMemo(() => {
    if (typeof window === 'undefined') return '';
    const url = new URL(window.location.href);
    url.searchParams.set('scenario', encodeTrialDesign(trialDesign));
    return url.toString();
  }, [trialDesign]);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <CardTitle>Scenario Explorer</CardTitle>
        <div className="flex flex-wrap items-center gap-2">
          {isRecalculating && (
            <span className="text-xs text-muted-foreground">Recalculating…</span>
          )}
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={onReset}
            data-testid="scenario-reset"
          >
            <RotateCcw className="mr-1 h-3.5 w-3.5" /> Reset
          </Button>
          {onSaveScenario && (
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => setSaveOpen(true)}
              data-testid="scenario-save"
            >
              <Save className="mr-1 h-3.5 w-3.5" /> Save scenario
            </Button>
          )}
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => {
              if (!shareLink) return;
              navigator.clipboard?.writeText(shareLink);
              toast.success('Scenario link copied');
            }}
            data-testid="scenario-copy-link"
          >
            <Copy className="mr-1 h-3.5 w-3.5" /> Copy link
          </Button>
          {savedScenarios.length > 0 && onLoadScenario && (
            <Select
              onValueChange={(id) => {
                const scenario = savedScenarios.find((s) => s.id === id || s.name === id);
                if (scenario) onLoadScenario(scenario);
              }}
            >
              <SelectTrigger className="h-8 w-44 text-xs">
                <SelectValue placeholder="Load scenario" />
              </SelectTrigger>
              <SelectContent>
                {savedScenarios.map((s) => (
                  <SelectItem key={s.id ?? s.name} value={s.id ?? s.name}>
                    {s.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </div>
      </CardHeader>
      <CardContent className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className={highlightClass('Enrollment size')}>
          <label className="text-xs font-medium" htmlFor="se-enrollment">
            Enrollment (n = {enrollment})
          </label>
          <div className="mt-1 flex items-center gap-2">
            <Slider
              id="se-enrollment"
              value={enrollment}
              min={20}
              max={2000}
              step={10}
              onValueChange={(v) => patch({ enrollment: v })}
            />
            <Input
              type="number"
              min={20}
              max={2000}
              value={enrollment}
              onChange={(e) => patch({ enrollment: Number(e.target.value) })}
              className="w-24"
            />
          </div>
        </div>

        <div className={highlightClass('Statistical power')}>
          <label className="text-xs font-medium" htmlFor="se-power">
            Statistical power ({power.toFixed(2)})
          </label>
          <div className="mt-1 flex items-center gap-2">
            <Slider
              id="se-power"
              value={power}
              min={0.6}
              max={0.95}
              step={0.01}
              onValueChange={(v) => patch({ statistical_power: v })}
            />
            <Input
              type="number"
              min={0.6}
              max={0.95}
              step={0.01}
              value={power}
              onChange={(e) => patch({ statistical_power: Number(e.target.value) })}
              className="w-24"
            />
          </div>
        </div>

        <div>
          <label className="text-xs font-medium" htmlFor="se-duration">
            Trial duration ({duration} months)
          </label>
          <div className="mt-1 flex items-center gap-2">
            <Slider
              id="se-duration"
              value={duration}
              min={6}
              max={60}
              step={1}
              onValueChange={(v) => patch({ duration_months: v })}
            />
            <Input
              type="number"
              min={6}
              max={60}
              value={duration}
              onChange={(e) => patch({ duration_months: Number(e.target.value) })}
              className="w-24"
            />
          </div>
        </div>

        <div>
          <label className="text-xs font-medium">Alpha (significance level)</label>
          <Select value={alpha} onValueChange={(v) => patch({ alpha: Number(v) })}>
            <SelectTrigger className="mt-1">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {ALPHA_OPTIONS.map((opt) => (
                <SelectItem key={opt} value={opt}>
                  {opt}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {endpointOptions.length > 0 && (
          <div>
            <label className="text-xs font-medium">Primary endpoint</label>
            <Select
              value={trialDesign.endpoint ?? endpointOptions[0]?.value}
              onValueChange={(v) => patch({ endpoint: v })}
            >
              <SelectTrigger className="mt-1">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {endpointOptions.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}

        <div>
          <label className="flex items-center gap-2 text-xs font-medium">
            <input
              type="checkbox"
              checked={enrichment}
              onChange={(e) => patch({ patient_enrichment: e.target.checked })}
            />
            Patient enrichment
          </label>
          {enrichment && (
            <Textarea
              className="mt-2"
              placeholder="Enrichment criteria"
              value={trialDesign.enrichment_criteria ?? ''}
              onChange={(e) => patch({ enrichment_criteria: e.target.value })}
            />
          )}
        </div>

        <div className="md:col-span-2">
          <button
            type="button"
            className="text-xs font-medium text-primary hover:underline"
            onClick={() => setAdvancedOpen((s) => !s)}
          >
            {advancedOpen ? '▾' : '▸'} Advanced
          </button>
          {advancedOpen && (
            <div className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-2">
              <Textarea
                placeholder="Inclusion criteria (comma-separated)"
                value={trialDesign.inclusion_criteria ?? ''}
                onChange={(e) => patch({ inclusion_criteria: e.target.value })}
              />
              <Textarea
                placeholder="Exclusion criteria (comma-separated)"
                value={trialDesign.exclusion_criteria ?? ''}
                onChange={(e) => patch({ exclusion_criteria: e.target.value })}
              />
              <Input
                placeholder="Biomarker stratification"
                value={trialDesign.biomarker_stratification ?? ''}
                onChange={(e) => patch({ biomarker_stratification: e.target.value })}
              />
            </div>
          )}
        </div>
      </CardContent>

      <Dialog open={saveOpen} onOpenChange={setSaveOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Save scenario</DialogTitle>
          </DialogHeader>
          <Input
            placeholder="Scenario name"
            value={scenarioName}
            onChange={(e) => setScenarioName(e.target.value)}
          />
          <DialogFooter>
            <Button variant="ghost" onClick={() => setSaveOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={async () => {
                if (!scenarioName.trim() || !onSaveScenario) return;
                await onSaveScenario(scenarioName.trim(), trialDesign);
                setScenarioName('');
                setSaveOpen(false);
                toast.success('Scenario saved');
              }}
            >
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
