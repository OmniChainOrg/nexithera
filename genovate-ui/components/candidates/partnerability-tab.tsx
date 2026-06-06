'use client';

import { useMemo, useState } from 'react';
import {
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
} from 'recharts';
import { RefreshCw, Search, Star, Download } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Slider } from '@/components/ui/slider';
import { Tooltip } from '@/components/ui/tooltip';
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
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { LoadingSpinner } from '@/components/common/loading-spinner';
import { EmptyState } from '@/components/common/empty-state';
import { usePartnerability } from '@/lib/hooks/use-partnerability';
import {
  fitScoreColor,
  filterPartners,
  getShortlist,
  initialsFor,
  sortPartners,
  toggleShortlist,
  type PartnerSort,
} from '@/lib/utils/partner-matchmaker';
import {
  bdSummaryToText,
  buildBDSummary,
} from '@/lib/utils/bd-summary';
import type {
  CompetitorEntry,
  PartnerabilityResponse,
} from '@/lib/api/partnerability';
import { cn } from '@/lib/utils/cn';
import toast from 'react-hot-toast';

interface PartnerabilityTabProps {
  candidateId: string;
  candidateName?: string;
  candidatePhase?: string;
}

const RADAR_COLOR = '#8b5cf6';

export function PartnerabilityTab({
  candidateId,
  candidateName,
  candidatePhase,
}: PartnerabilityTabProps) {
  const { data, isLoading, isFetching, refetch, error } =
    usePartnerability(candidateId);

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <LoadingSpinner />
      </div>
    );
  }
  if (error || !data) {
    return (
      <EmptyState
        title="No partnerability data"
        description={
          error ? 'Failed to load partnerability data. Retry?' : 'Run partnerability analysis first.'
        }
        action={
          <Button onClick={() => refetch()} variant="outline">
            <RefreshCw className="mr-2 h-4 w-4" />
            Retry
          </Button>
        }
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold">Partnerability</h2>
        <Button
          variant="outline"
          size="sm"
          onClick={() => refetch()}
          disabled={isFetching}
        >
          <RefreshCw className={cn('mr-2 h-4 w-4', isFetching && 'animate-spin')} />
          Refresh
        </Button>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Score Radar</CardTitle>
          </CardHeader>
          <CardContent>
            <PartnerabilityRadar data={data} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Overall Score</CardTitle>
          </CardHeader>
          <CardContent>
            <ScoreGauge score={data.overall_score} verdict={data.verdict} />
          </CardContent>
        </Card>
      </div>

      <BreakdownCards data={data} />

      <div className="grid gap-6 xl:grid-cols-3">
        <div className="xl:col-span-2">
          <CompetitorTable
            competitors={data.competitive_landscape?.competitors ?? []}
          />
        </div>
        <div>
          <PartnerMatchmaker
            data={data}
            candidateName={candidateName}
            candidatePhase={candidatePhase}
          />
        </div>
      </div>
    </div>
  );
}

// ============================================================
// Radar
// ============================================================

function PartnerabilityRadar({ data }: { data: PartnerabilityResponse }) {
  const radarData = [
    { dim: 'Competitive Moat', value: data.competitive_moat },
    { dim: 'IP Strength', value: data.ip_strength },
    { dim: 'Unmet Need', value: data.unmet_need },
    { dim: 'IND Readiness', value: data.ind_readiness },
  ];
  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={radarData} outerRadius="75%">
          <PolarGrid stroke="hsl(var(--border))" />
          <PolarAngleAxis dataKey="dim" tick={{ fontSize: 11 }} />
          <Radar
            name="Score"
            dataKey="value"
            stroke={RADAR_COLOR}
            fill={RADAR_COLOR}
            fillOpacity={0.3}
          />
          <RechartsTooltip
            formatter={(value: number) => [`${value.toFixed(1)} / 10`, 'Score']}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ============================================================
// Gauge
// ============================================================

function ScoreGauge({ score, verdict }: { score: number; verdict: string }) {
  const pct = Math.max(0, Math.min(1, score / 10));
  const color =
    score >= 7 ? '#10b981' : score >= 4 ? '#f59e0b' : '#ef4444';
  const label =
    score >= 7
      ? 'Highly Partnerable'
      : score >= 4
      ? 'Moderate Partnerability'
      : 'Low Partnerability';

  const radius = 60;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - pct);

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative h-40 w-40">
        <svg viewBox="0 0 160 160" className="h-full w-full -rotate-90">
          <circle
            cx={80}
            cy={80}
            r={radius}
            stroke="hsl(var(--muted))"
            strokeWidth={12}
            fill="none"
          />
          <circle
            cx={80}
            cy={80}
            r={radius}
            stroke={color}
            strokeWidth={12}
            fill="none"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            style={{ transition: 'stroke-dashoffset 0.5s ease' }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-3xl font-bold" style={{ color }}>
            {score.toFixed(1)}
          </span>
          <span className="text-xs text-muted-foreground">out of 10</span>
        </div>
      </div>
      <p className="text-sm font-medium" style={{ color }}>
        {label}
      </p>
      <p className="text-center text-xs text-muted-foreground">{verdict}</p>
    </div>
  );
}

// ============================================================
// Breakdown cards
// ============================================================

function BreakdownCards({ data }: { data: PartnerabilityResponse }) {
  const cards = [
    {
      label: 'Competitive Moat',
      value: data.competitive_moat,
      description: 'Differentiation vs. landscape',
    },
    {
      label: 'IP Strength',
      value: data.ip_strength,
      description: 'Patent position & freedom-to-operate',
    },
    {
      label: 'Unmet Need',
      value: data.unmet_need,
      description: 'Market gap vs. current standard',
    },
    {
      label: 'IND Readiness',
      value: data.ind_readiness,
      description: 'Distance to IND filing',
    },
  ];
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      {cards.map((c) => (
        <Card key={c.label}>
          <CardContent className="p-4">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              {c.label}
            </p>
            <p className="mt-1 text-3xl font-semibold">{c.value.toFixed(1)}</p>
            <p className="mt-1 text-xs text-muted-foreground">{c.description}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

// ============================================================
// Competitor table
// ============================================================

type CompetitorSortKey = keyof Pick<
  CompetitorEntry,
  'asset_name' | 'developer' | 'phase' | 'modality' | 'threat_level' | 'source'
>;

const THREAT_BADGE: Record<string, { dot: string; label: string }> = {
  high: { dot: 'bg-red-500', label: 'High' },
  medium: { dot: 'bg-amber-500', label: 'Medium' },
  low: { dot: 'bg-emerald-500', label: 'Low' },
};

function CompetitorTable({ competitors }: { competitors: CompetitorEntry[] }) {
  const [sortKey, setSortKey] = useState<CompetitorSortKey>('threat_level');
  const [sortAsc, setSortAsc] = useState(true);
  const [search, setSearch] = useState('');
  const [threatFilter, setThreatFilter] = useState<Set<string>>(new Set());
  const [phaseFilter, setPhaseFilter] = useState<Set<string>>(new Set());
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(10);
  const [selected, setSelected] = useState<CompetitorEntry | null>(null);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return competitors.filter((c) => {
      if (q) {
        const hay = `${c.asset_name} ${c.developer ?? ''}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      if (threatFilter.size && !threatFilter.has(c.threat_level ?? '')) return false;
      if (phaseFilter.size && !phaseFilter.has(c.phase ?? '')) return false;
      return true;
    });
  }, [competitors, search, threatFilter, phaseFilter]);

  const sorted = useMemo(() => {
    const arr = filtered.slice();
    arr.sort((a, b) => {
      const av = (a[sortKey] ?? '') as string;
      const bv = (b[sortKey] ?? '') as string;
      return sortAsc ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
    });
    return arr;
  }, [filtered, sortKey, sortAsc]);

  const paged = sorted.slice(page * pageSize, page * pageSize + pageSize);
  const phases = Array.from(new Set(competitors.map((c) => c.phase).filter(Boolean) as string[]));

  if (competitors.length === 0) {
    return (
      <EmptyState
        title="No competitors found"
        description="Run competitive landscape analysis first."
      />
    );
  }

  function toggle(set: Set<string>, key: string, setter: (s: Set<string>) => void) {
    const next = new Set(set);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    setter(next);
    setPage(0);
  }

  function exportCSV() {
    const headers = [
      'Asset',
      'Developer',
      'Phase',
      'Modality',
      'Threat',
      'Differentiation',
      'Source',
    ];
    const rows = sorted.map((c) =>
      [
        c.asset_name,
        c.developer ?? '',
        c.phase ?? '',
        c.modality ?? '',
        c.threat_level ?? '',
        (c.differentiation ?? '').replace(/"/g, '""'),
        c.source ?? '',
      ]
        .map((v) => `"${v}"`)
        .join(','),
    );
    const csv = [headers.join(','), ...rows].join('\n');
    downloadBlob(csv, 'text/csv', 'competitive-landscape.csv');
  }

  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2">
        <CardTitle>Competitive Landscape</CardTitle>
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <Search className="absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(0);
              }}
              placeholder="Search asset or developer"
              className="h-9 pl-8"
            />
          </div>
          <Button variant="outline" size="sm" onClick={exportCSV}>
            <Download className="mr-1 h-4 w-4" /> CSV
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center gap-3 text-xs">
          <span className="font-medium">Threat:</span>
          {(['high', 'medium', 'low'] as const).map((t) => (
            <label key={t} className="flex items-center gap-1">
              <input
                type="checkbox"
                checked={threatFilter.has(t)}
                onChange={() => toggle(threatFilter, t, setThreatFilter)}
              />
              {t}
            </label>
          ))}
          {phases.length > 0 && (
            <>
              <span className="ml-2 font-medium">Phase:</span>
              {phases.map((p) => (
                <label key={p} className="flex items-center gap-1">
                  <input
                    type="checkbox"
                    checked={phaseFilter.has(p)}
                    onChange={() => toggle(phaseFilter, p, setPhaseFilter)}
                  />
                  {p}
                </label>
              ))}
            </>
          )}
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm">
            <thead className="border-b text-left text-xs uppercase text-muted-foreground">
              <tr>
                {(
                  [
                    ['asset_name', 'Asset'],
                    ['developer', 'Developer'],
                    ['phase', 'Phase'],
                    ['modality', 'Modality'],
                    ['threat_level', 'Threat'],
                  ] as [CompetitorSortKey, string][]
                ).map(([k, label]) => (
                  <th
                    key={k}
                    className="cursor-pointer px-2 py-2"
                    onClick={() => {
                      if (sortKey === k) setSortAsc((v) => !v);
                      else {
                        setSortKey(k);
                        setSortAsc(true);
                      }
                    }}
                  >
                    {label} {sortKey === k ? (sortAsc ? '▲' : '▼') : ''}
                  </th>
                ))}
                <th className="px-2 py-2">Differentiation</th>
                <th className="px-2 py-2">Source</th>
                <th className="px-2 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {paged.map((c, idx) => (
                <tr
                  key={(c.id ?? c.asset_name) + idx}
                  className="border-b last:border-0 hover:bg-muted/40"
                >
                  <td className="px-2 py-2 font-semibold">{c.asset_name}</td>
                  <td className="px-2 py-2">{c.developer ?? '—'}</td>
                  <td className="px-2 py-2">
                    {c.phase ? <Badge variant="outline">{c.phase}</Badge> : '—'}
                  </td>
                  <td className="px-2 py-2">
                    {c.modality ? <Badge variant="secondary">{c.modality}</Badge> : '—'}
                  </td>
                  <td className="px-2 py-2">
                    {c.threat_level ? (
                      <span className="inline-flex items-center gap-1">
                        <span
                          className={cn(
                            'h-2.5 w-2.5 rounded-full',
                            THREAT_BADGE[c.threat_level]?.dot ?? 'bg-gray-400',
                          )}
                        />
                        {THREAT_BADGE[c.threat_level]?.label ?? c.threat_level}
                      </span>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td className="max-w-xs truncate px-2 py-2" title={c.differentiation ?? ''}>
                    {c.differentiation ?? '—'}
                  </td>
                  <td className="px-2 py-2">
                    {c.source ? <Badge variant="outline">{c.source}</Badge> : '—'}
                  </td>
                  <td className="px-2 py-2">
                    <Button size="sm" variant="ghost" onClick={() => setSelected(c)}>
                      Details
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <div>
            Showing {paged.length} of {sorted.length}
          </div>
          <div className="flex items-center gap-2">
            <Select
              value={String(pageSize)}
              onValueChange={(v) => {
                setPageSize(Number(v));
                setPage(0);
              }}
            >
              <SelectTrigger className="h-8 w-20">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {[10, 25, 50].map((n) => (
                  <SelectItem key={n} value={String(n)}>
                    {n}/page
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              size="sm"
              variant="outline"
              disabled={page === 0}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
            >
              Prev
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={(page + 1) * pageSize >= sorted.length}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      </CardContent>

      <Dialog open={!!selected} onOpenChange={(o) => !o && setSelected(null)}>
        <DialogContent>
          {selected && (
            <>
              <DialogHeader>
                <DialogTitle>{selected.asset_name}</DialogTitle>
              </DialogHeader>
              <div className="space-y-2 text-sm">
                {selected.developer && (
                  <p>
                    <span className="font-medium">Developer:</span> {selected.developer}
                  </p>
                )}
                {selected.mechanism && (
                  <p>
                    <span className="font-medium">Mechanism:</span> {selected.mechanism}
                  </p>
                )}
                {selected.estimated_launch_year && (
                  <p>
                    <span className="font-medium">Estimated launch:</span>{' '}
                    {selected.estimated_launch_year}
                  </p>
                )}
                {selected.source_ref && (
                  <p>
                    <a
                      href={selected.source_ref}
                      target="_blank"
                      rel="noreferrer"
                      className="text-primary underline"
                    >
                      Source reference
                    </a>
                  </p>
                )}
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    addToWatchlist(selected.asset_name);
                    toast.success('Added to watchlist');
                  }}
                >
                  <Star className="mr-1 h-4 w-4" /> Add to watchlist
                </Button>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </Card>
  );
}

// ============================================================
// Partner Matchmaker
// ============================================================

function PartnerMatchmaker({
  data,
  candidateName,
  candidatePhase,
}: {
  data: PartnerabilityResponse;
  candidateName?: string;
  candidatePhase?: string;
}) {
  const [sort, setSort] = useState<PartnerSort>('fit_desc');
  const [minFit, setMinFit] = useState(0);
  const [search, setSearch] = useState('');
  const [shortlist, setShortlist] = useState<string[]>(() => getShortlist());
  const [showShortlist, setShowShortlist] = useState(false);

  const partners = useMemo(
    () => sortPartners(filterPartners(data.potential_partners ?? [], { minFitScore: minFit, search }), sort),
    [data.potential_partners, sort, minFit, search],
  );

  function onShortlist(name: string) {
    setShortlist(toggleShortlist(name));
  }

  function exportSummary() {
    const doc = buildBDSummary({
      partnerability: data,
      candidateName,
      candidatePhase,
      indReadiness: data.ind_readiness_assessment,
      competitors: data.competitive_landscape?.competitors,
    });
    void exportBDSummaryPDF(doc).catch(() => {
      downloadBlob(bdSummaryToText(doc), 'text/plain', `bd-summary-${data.candidate_id}.txt`);
    });
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>Partner Matchmaker</span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowShortlist(true)}
            disabled={shortlist.length === 0}
          >
            Shortlist ({shortlist.length})
          </Button>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="space-y-2">
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search company"
            className="h-9"
          />
          <div className="flex items-center gap-2">
            <Select value={sort} onValueChange={(v) => setSort(v as PartnerSort)}>
              <SelectTrigger className="h-9 w-44">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="fit_desc">Fit score (high → low)</SelectItem>
                <SelectItem value="alphabetical">Alphabetical</SelectItem>
                <SelectItem value="strategic">Strategic fit</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <span className="w-24 text-muted-foreground">Min fit ≥ {minFit}</span>
            <Slider value={minFit} min={0} max={10} step={0.5} onValueChange={setMinFit} />
          </div>
        </div>

        {partners.length === 0 ? (
          <EmptyState
            title="No partner matches"
            description="No partners match these filters."
          />
        ) : (
          <div className="grid grid-cols-1 gap-3">
            {partners.map((p) => {
              const color = fitScoreColor(p.fit_score);
              const isShort = shortlist.includes(p.name);
              return (
                <div
                  key={p.name}
                  className="flex items-start gap-3 rounded-lg border p-3"
                >
                  <div
                    className={cn(
                      'flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-semibold',
                      color.bg,
                      color.text,
                    )}
                  >
                    {initialsFor(p.name)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <p className="truncate font-semibold">{p.name}</p>
                      <button
                        type="button"
                        onClick={() => onShortlist(p.name)}
                        aria-label="Toggle shortlist"
                      >
                        <Star
                          className={cn(
                            'h-4 w-4',
                            isShort
                              ? 'fill-amber-400 text-amber-500'
                              : 'text-muted-foreground',
                          )}
                        />
                      </button>
                    </div>
                    <div className="flex items-center gap-2 text-xs">
                      <span className={cn('font-bold', color.text)}>
                        {p.fit_score.toFixed(1)}
                      </span>
                      <span className="text-muted-foreground">out of 10</span>
                      {p.focus_overlap && (
                        <Badge variant="secondary" className="text-[10px]">
                          Focus overlap
                        </Badge>
                      )}
                    </div>
                    <Tooltip content={p.rationale}>
                      <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
                        {p.rationale}
                      </p>
                    </Tooltip>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        <Button variant="default" className="w-full" onClick={exportSummary}>
          <Download className="mr-1 h-4 w-4" /> Export BD Summary
        </Button>
      </CardContent>

      <Dialog open={showShortlist} onOpenChange={setShowShortlist}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Shortlisted Partners</DialogTitle>
          </DialogHeader>
          <ul className="space-y-2">
            {shortlist.map((n) => (
              <li key={n} className="flex items-center justify-between text-sm">
                <span>{n}</span>
                <Button size="sm" variant="ghost" onClick={() => onShortlist(n)}>
                  Remove
                </Button>
              </li>
            ))}
          </ul>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

// ============================================================
// Helpers
// ============================================================

function downloadBlob(data: string, mime: string, filename: string) {
  if (typeof window === 'undefined') return;
  const blob = new Blob([data], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function addToWatchlist(name: string) {
  if (typeof window === 'undefined') return;
  try {
    const raw = window.localStorage.getItem('competitor_watchlist');
    const arr: string[] = raw ? JSON.parse(raw) : [];
    if (!arr.includes(name)) arr.push(name);
    window.localStorage.setItem('competitor_watchlist', JSON.stringify(arr));
  } catch {
    /* ignore */
  }
}

/**
 * PDF export uses jsPDF when available (dynamic import) and falls back to a
 * plain-text download — keeping the build dep-free while still supporting
 * the BD workflow when the library is installed.
 */
async function exportBDSummaryPDF(
  doc: ReturnType<typeof buildBDSummary>,
): Promise<void> {
  const text = bdSummaryToText(doc);
  try {
    const dynImport: (m: string) => Promise<unknown> = (m) =>
      (Function('m', 'return import(m)') as (m: string) => Promise<unknown>)(m);
    const mod = (await dynImport('jspdf').catch(() => null)) as
      | { jsPDF?: new (opts: unknown) => unknown; default?: new (opts: unknown) => unknown }
      | null;
    if (!mod) throw new Error('jspdf not installed');
    const Ctor = (mod.jsPDF ?? mod.default) as new (opts: unknown) => {
      splitTextToSize(t: string, w: number): string[];
      text(t: string[], x: number, y: number): void;
      save(name: string): void;
    };
    const pdf = new Ctor({ unit: 'pt', format: 'letter' });
    const lines = pdf.splitTextToSize(text, 500);
    pdf.text(lines, 40, 60);
    pdf.save(`bd-summary-${doc.candidate.id}.pdf`);
  } catch {
    downloadBlob(text, 'text/plain', `bd-summary-${doc.candidate.id}.txt`);
  }
}
