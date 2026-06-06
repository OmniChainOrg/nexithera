'use client';

import { useMemo, useState } from 'react';
import { ExternalLink, Search } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Progress } from '@/components/ui/progress';
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
import { EmptyState } from '@/components/common/empty-state';
import {
  type PrecedentOutcomeFilter,
  type PrecedentSortKey,
  filterPrecedents,
  formatProbability,
  paginate,
} from '@/lib/utils/clinical-forecast';
import type { ClinicalPrecedent } from '@/lib/api/forecast';

interface PrecedentBrowserProps {
  precedents: ClinicalPrecedent[] | null | undefined;
}

const PAGE_SIZE_OPTIONS = [10, 25, 50];

export function PrecedentBrowser({ precedents }: PrecedentBrowserProps) {
  const [search, setSearch] = useState('');
  const [outcome, setOutcome] = useState<PrecedentOutcomeFilter>('all');
  const [phase, setPhase] = useState<string>('all');
  const [modality, setModality] = useState<string>('all');
  const [sortBy, setSortBy] = useState<PrecedentSortKey>('similarity');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [active, setActive] = useState<ClinicalPrecedent | null>(null);

  const phases = useMemo(
    () => Array.from(new Set((precedents ?? []).map((p) => p.phase).filter(Boolean) as string[])),
    [precedents],
  );
  const modalities = useMemo(
    () =>
      Array.from(
        new Set((precedents ?? []).map((p) => p.modality).filter(Boolean) as string[]),
      ),
    [precedents],
  );

  const filtered = useMemo(
    () =>
      filterPrecedents(precedents, {
        search,
        outcome,
        phase,
        modality,
        sortBy,
        sortDirection: 'desc',
      }),
    [precedents, search, outcome, phase, modality, sortBy],
  );

  const pageRows = paginate(filtered, page, pageSize);
  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));

  if (!precedents || precedents.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Historical precedents</CardTitle>
        </CardHeader>
        <CardContent>
          <EmptyState
            title="No precedents found"
            description="Seed clinical_precedents table with historical trials to influence this forecast."
          />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Historical precedents ({filtered.length})</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search trial / target / disease"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              className="w-64 pl-8"
              data-testid="precedent-search"
            />
          </div>
          <Select
            value={outcome}
            onValueChange={(v) => {
              setOutcome(v as PrecedentOutcomeFilter);
              setPage(1);
            }}
          >
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All outcomes</SelectItem>
              <SelectItem value="success">Success</SelectItem>
              <SelectItem value="fail">Fail</SelectItem>
            </SelectContent>
          </Select>
          {phases.length > 0 && (
            <Select
              value={phase}
              onValueChange={(v) => {
                setPhase(v);
                setPage(1);
              }}
            >
              <SelectTrigger className="w-32">
                <SelectValue placeholder="Phase" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All phases</SelectItem>
                {phases.map((p) => (
                  <SelectItem key={p} value={p}>
                    {p}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          {modalities.length > 0 && (
            <Select
              value={modality}
              onValueChange={(v) => {
                setModality(v);
                setPage(1);
              }}
            >
              <SelectTrigger className="w-40">
                <SelectValue placeholder="Modality" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All modalities</SelectItem>
                {modalities.map((m) => (
                  <SelectItem key={m} value={m}>
                    {m}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          <Select value={sortBy} onValueChange={(v) => setSortBy(v as PrecedentSortKey)}>
            <SelectTrigger className="w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="similarity">Sort by similarity</SelectItem>
              <SelectItem value="effect_size">Sort by effect size</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="overflow-x-auto rounded-md border">
          <table className="w-full min-w-[800px] text-left text-xs">
            <thead className="bg-muted/40 text-muted-foreground">
              <tr>
                <th className="p-2">Trial ID</th>
                <th className="p-2">Phase</th>
                <th className="p-2">Modality</th>
                <th className="p-2">Target</th>
                <th className="p-2">Disease</th>
                <th className="p-2">Similarity</th>
                <th className="p-2">Outcome</th>
                <th className="p-2">Effect size</th>
                <th className="p-2"></th>
              </tr>
            </thead>
            <tbody>
              {pageRows.map((row) => (
                <tr
                  key={row.trial_id}
                  className="cursor-pointer border-t hover:bg-muted/30"
                  onClick={() => setActive(row)}
                  data-testid={`precedent-row-${row.trial_id}`}
                >
                  <td className="p-2">
                    <a
                      href={`https://clinicaltrials.gov/study/${encodeURIComponent(row.trial_id)}`}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 text-primary underline"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {row.trial_id}
                      <ExternalLink className="h-3 w-3" />
                    </a>
                  </td>
                  <td className="p-2">
                    {row.phase ? <Badge variant="outline">{row.phase}</Badge> : '—'}
                  </td>
                  <td className="p-2">
                    {row.modality ? <Badge variant="secondary">{row.modality}</Badge> : '—'}
                  </td>
                  <td className="p-2">{row.target ?? '—'}</td>
                  <td className="p-2">{row.disease ?? '—'}</td>
                  <td className="p-2">
                    <div className="flex items-center gap-2">
                      <Progress
                        value={Math.round((row.similarity ?? 0) * 100)}
                        className="w-24"
                      />
                      <span>{formatProbability(row.similarity ?? 0)}</span>
                    </div>
                  </td>
                  <td className="p-2">
                    <Badge
                      variant={
                        row.outcome === 'success' ? 'default' : 'destructive'
                      }
                    >
                      {row.outcome === 'success' ? 'Success' : 'Fail'}
                    </Badge>
                  </td>
                  <td className="p-2 tabular-nums">
                    {row.effect_size != null ? row.effect_size.toFixed(2) : '—'}
                  </td>
                  <td className="p-2 text-right">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={(e) => {
                        e.stopPropagation();
                        setActive(row);
                      }}
                    >
                      Details
                    </Button>
                  </td>
                </tr>
              ))}
              {pageRows.length === 0 && (
                <tr>
                  <td colSpan={9} className="p-6 text-center text-muted-foreground">
                    No precedents match the current filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <div className="flex items-center gap-2">
            Rows per page
            <Select value={String(pageSize)} onValueChange={(v) => setPageSize(Number(v))}>
              <SelectTrigger className="h-8 w-20">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PAGE_SIZE_OPTIONS.map((opt) => (
                  <SelectItem key={opt} value={String(opt)}>
                    {opt}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="ghost"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              Prev
            </Button>
            <span>
              {page} / {pageCount}
            </span>
            <Button
              size="sm"
              variant="ghost"
              disabled={page >= pageCount}
              onClick={() => setPage((p) => Math.min(pageCount, p + 1))}
            >
              Next
            </Button>
          </div>
        </div>
      </CardContent>

      <Dialog open={!!active} onOpenChange={(o) => !o && setActive(null)}>
        <DialogContent className="max-w-2xl">
          {active && (
            <>
              <DialogHeader>
                <DialogTitle>
                  {active.title ?? active.trial_id}{' '}
                  <Badge variant="outline" className="ml-2">
                    {active.phase ?? 'Phase ?'}
                  </Badge>
                </DialogTitle>
              </DialogHeader>
              <div className="space-y-3 text-sm">
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <strong>Trial ID:</strong> {active.trial_id}
                  </div>
                  <div>
                    <strong>Status:</strong> {active.status ?? '—'}
                  </div>
                  <div>
                    <strong>Enrollment:</strong> {active.enrollment ?? '—'}
                  </div>
                  <div>
                    <strong>Effect size:</strong>{' '}
                    {active.effect_size != null ? active.effect_size.toFixed(2) : '—'}
                  </div>
                  <div>
                    <strong>Start:</strong> {active.start_date ?? '—'}
                  </div>
                  <div>
                    <strong>Completion:</strong> {active.completion_date ?? '—'}
                  </div>
                </div>
                {active.primary_endpoint && (
                  <p>
                    <strong>Primary endpoint:</strong> {active.primary_endpoint}
                  </p>
                )}
                {active.secondary_endpoints?.length ? (
                  <p>
                    <strong>Secondary:</strong> {active.secondary_endpoints.join(', ')}
                  </p>
                ) : null}
                {active.inclusion_criteria_summary && (
                  <p>
                    <strong>Inclusion:</strong> {active.inclusion_criteria_summary}
                  </p>
                )}
                {active.exclusion_criteria_summary && (
                  <p>
                    <strong>Exclusion:</strong> {active.exclusion_criteria_summary}
                  </p>
                )}
                {active.publication_references?.length ? (
                  <div>
                    <strong>Publications:</strong>
                    <ul className="ml-4 list-disc">
                      {active.publication_references.map((ref) => (
                        <li key={ref}>
                          <a
                            href={
                              ref.startsWith('http')
                                ? ref
                                : `https://pubmed.ncbi.nlm.nih.gov/?term=${encodeURIComponent(ref)}`
                            }
                            target="_blank"
                            rel="noreferrer"
                            className="text-primary underline"
                          >
                            {ref}
                          </a>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {active.similarity_breakdown && (
                  <div>
                    <strong>Why similar:</strong>
                    <ul className="mt-1 grid grid-cols-2 gap-1 text-xs">
                      {Object.entries(active.similarity_breakdown).map(([k, v]) => (
                        <li key={k}>
                          {k}: {formatProbability(v)}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {active.weight != null && (
                  <p className="text-xs text-muted-foreground">
                    Contributed with weight {active.weight.toFixed(2)} to the precedent agent.
                  </p>
                )}
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </Card>
  );
}
