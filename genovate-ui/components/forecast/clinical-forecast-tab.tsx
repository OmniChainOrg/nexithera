'use client';

import { useEffect, useMemo, useState } from 'react';
import { ShieldCheck } from 'lucide-react';
import toast from 'react-hot-toast';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { LoadingSpinner } from '@/components/common/loading-spinner';
import { EmptyState } from '@/components/common/empty-state';
import { ForecastGauge } from './forecast-gauge';
import { DecompositionBars } from './decomposition-bars';
import { TornadoPlot } from './tornado-plot';
import { ScenarioExplorer } from './scenario-explorer';
import { PrecedentBrowser } from './precedent-browser';
import { ForecastHistoryChart } from './forecast-history-chart';
import {
  useClinicalForecast,
  useForecastHistory,
  useSubmitForecastToGuardian,
} from '@/lib/hooks/use-forecast';
import { useDebouncedValue } from '@/lib/hooks/use-debounced-value';
import { useProgramEvents } from '@/lib/hooks/use-websocket';
import { ApiError } from '@/lib/api/client';
import type { SavedScenario, TrialDesign } from '@/lib/api/forecast';
import { decodeTrialDesign } from '@/lib/utils/clinical-forecast';

interface ClinicalForecastTabProps {
  candidateId: string;
  candidatePhase?: string;
  programId?: string;
  /** Optional primary-endpoint options from the candidate's trial design. */
  endpointOptions?: { value: string; label: string }[];
}

const DEFAULT_TRIAL_DESIGN: TrialDesign = {
  enrollment: 120,
  duration_months: 12,
  statistical_power: 0.8,
  alpha: 0.05,
};

export function ClinicalForecastTab({
  candidateId,
  candidatePhase,
  programId,
  endpointOptions = [],
}: ClinicalForecastTabProps) {
  // Hydrate from ?scenario= query param when present (shareable links).
  const initialDesign = useMemo<TrialDesign>(() => {
    if (typeof window === 'undefined') return DEFAULT_TRIAL_DESIGN;
    const token = new URL(window.location.href).searchParams.get('scenario');
    if (!token) return DEFAULT_TRIAL_DESIGN;
    return { ...DEFAULT_TRIAL_DESIGN, ...(decodeTrialDesign(token) ?? {}) };
  }, []);

  const [trialDesign, setTrialDesign] = useState<TrialDesign>(initialDesign);
  const [baseTrialDesign, setBaseTrialDesign] = useState<TrialDesign>(initialDesign);
  const [focusedFactor, setFocusedFactor] = useState<string | null>(null);
  const [savedScenarios, setSavedScenarios] = useState<SavedScenario[]>([]);
  const [showHistory, setShowHistory] = useState(true);
  const [showPrecedents, setShowPrecedents] = useState(true);
  const [showScenarios, setShowScenarios] = useState(true);

  // Debounce slider updates so we don't hammer the API while dragging.
  const debouncedDesign = useDebouncedValue(trialDesign, 500);

  const phase = candidatePhase ?? 'II';
  const {
    data: forecast,
    isLoading,
    isFetching,
    error,
    refetch,
  } = useClinicalForecast(candidateId, {
    phase,
    trial_design: debouncedDesign,
  });

  // Seed baseTrialDesign on first successful response so "Reset" works.
  useEffect(() => {
    if (forecast && baseTrialDesign === initialDesign) {
      const seeded: TrialDesign = {
        ...initialDesign,
        ...debouncedDesign,
      };
      setBaseTrialDesign(seeded);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [forecast?.forecast_id]);

  const history = useForecastHistory(candidateId);
  const submitGuardian = useSubmitForecastToGuardian(forecast?.forecast_id ?? null);

  // Listen for forecast.updated WS events on the program channel.
  useProgramEvents(programId ?? null, { enabled: !!programId });

  const handleReset = () => {
    setTrialDesign(baseTrialDesign);
    toast.success('Reset to current design');
  };

  const handleSave = (name: string, design: TrialDesign) => {
    const scenario: SavedScenario = {
      id: `local-${Date.now()}`,
      name,
      trial_design: design,
      probability: forecast?.probability ?? null,
      saved_at: new Date().toISOString(),
    };
    setSavedScenarios((prev) => [...prev, scenario]);
    // Best-effort persist via the forecast cache so the backend can pick it
    // up via the existing /forecast/clinical endpoint on next save. Full
    // server-side persistence would require a dedicated PATCH that the
    // backend doesn't yet expose; we surface the in-memory list for now.
  };

  const handleSubmitGuardian = async () => {
    if (!forecast?.forecast_id) return;
    const reviewerId =
      typeof window !== 'undefined' ? window.prompt('Reviewer ID (UUID):')?.trim() : null;
    if (!reviewerId) return;
    try {
      await submitGuardian.mutateAsync({
        reviewer_id: reviewerId,
        decision: 'pending',
        decision_rationale: 'Submitted from Clinical Forecast tab',
      });
      toast.success('Forecast submitted to Guardian');
    } catch (e) {
      const msg =
        e instanceof ApiError
          ? `Guardian rejected submission (${e.status})`
          : 'Failed to submit for Guardian review';
      toast.error(msg);
    }
  };

  if (isLoading && !forecast) {
    return (
      <div className="flex h-64 items-center justify-center">
        <LoadingSpinner />
      </div>
    );
  }

  if (error && !forecast) {
    const isNotFound = error instanceof ApiError && error.status === 404;
    return (
      <EmptyState
        title={isNotFound ? 'No forecast available' : 'Could not load forecast'}
        description={
          isNotFound
            ? 'Run the Clinical Forecaster agent for this candidate to generate a forecast.'
            : (error as Error).message
        }
        action={
          <Button onClick={() => refetch()} variant="outline" size="sm">
            Retry
          </Button>
        }
      />
    );
  }

  const probability = forecast?.probability ?? 0;
  const ci = forecast?.confidence_interval ?? null;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold">Clinical Forecast</h2>
          {forecast?.status && (
            <Badge variant="outline" data-testid="forecast-status-badge">
              {forecast.status}
            </Badge>
          )}
          {forecast?.verdict && (
            <span className="text-sm text-muted-foreground">{forecast.verdict}</span>
          )}
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={handleSubmitGuardian}
          disabled={!forecast?.forecast_id || submitGuardian.isPending}
        >
          <ShieldCheck className="mr-1 h-4 w-4" />
          Submit for Guardian Review
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Card className="md:col-span-1">
          <CardHeader>
            <CardTitle>Probability of success</CardTitle>
          </CardHeader>
          <CardContent className="flex items-center justify-center">
            <ForecastGauge
              probability={probability}
              confidenceInterval={ci}
              loading={isFetching}
            />
          </CardContent>
        </Card>

        <Card className="md:col-span-1">
          <CardHeader>
            <CardTitle>Decomposition</CardTitle>
          </CardHeader>
          <CardContent>
            <DecompositionBars
              decomposition={forecast?.decomposition ?? null}
              probability={probability}
            />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Sensitivity (tornado)</CardTitle>
        </CardHeader>
        <CardContent>
          <TornadoPlot
            sensitivity={forecast?.sensitivity ?? null}
            baseProbability={probability}
            onFactorClick={(factor) => {
              setFocusedFactor(factor);
              if (typeof document !== 'undefined') {
                document
                  .getElementById('scenario-explorer-anchor')
                  ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
              }
            }}
          />
        </CardContent>
      </Card>

      <div id="scenario-explorer-anchor">
        <button
          type="button"
          className="text-xs font-medium text-primary hover:underline"
          onClick={() => setShowScenarios((s) => !s)}
        >
          {showScenarios ? '▾' : '▸'} Scenario explorer
        </button>
        {showScenarios && (
          <div className="mt-2">
            <ScenarioExplorer
              baseTrialDesign={baseTrialDesign}
              trialDesign={trialDesign}
              onChange={setTrialDesign}
              onReset={handleReset}
              endpointOptions={endpointOptions}
              savedScenarios={savedScenarios}
              onSaveScenario={(name, design) => handleSave(name, design)}
              onLoadScenario={(s) => setTrialDesign(s.trial_design)}
              isRecalculating={isFetching}
              focusedFactor={focusedFactor}
            />
          </div>
        )}
      </div>

      <div>
        <button
          type="button"
          className="text-xs font-medium text-primary hover:underline"
          onClick={() => setShowPrecedents((s) => !s)}
        >
          {showPrecedents ? '▾' : '▸'} Precedent browser
        </button>
        {showPrecedents && (
          <div className="mt-2">
            <PrecedentBrowser precedents={forecast?.top_precedents ?? []} />
          </div>
        )}
      </div>

      <div>
        <button
          type="button"
          className="text-xs font-medium text-primary hover:underline"
          onClick={() => setShowHistory((s) => !s)}
        >
          {showHistory ? '▾' : '▸'} Forecast history
        </button>
        {showHistory && (
          <div className="mt-2">
            <ForecastHistoryChart
              events={history.data?.events ?? null}
              loading={history.isLoading}
            />
          </div>
        )}
      </div>
    </div>
  );
}
