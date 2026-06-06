'use client';

import { useMemo, useState } from 'react';
import { RefreshCw, Info, Download } from 'lucide-react';
import toast from 'react-hot-toast';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { LoadingSpinner } from '@/components/common/loading-spinner';
import { EmptyState } from '@/components/common/empty-state';
import { Tooltip } from '@/components/ui/tooltip';
import { usePartnerability } from '@/lib/hooks/use-partnerability';
import {
  buildPatentTimeline,
  type PatentBar,
} from '@/lib/utils/patent-timeline';
import type { IPPositionEntry } from '@/lib/api/partnerability';
import { cn } from '@/lib/utils/cn';

type Zoom = '5y' | '10y' | 'full';

interface PatentMapTabProps {
  candidateId: string;
  /** Optional IND filing year for the candidate marker. */
  indFilingYear?: number;
}

export function PatentMapTab({ candidateId, indFilingYear }: PatentMapTabProps) {
  const { data, isLoading, isFetching, refetch } = usePartnerability(candidateId);
  const [zoom, setZoom] = useState<Zoom>('full');
  const [showExpired, setShowExpired] = useState(false);
  const [selectedPatent, setSelectedPatent] = useState<IPPositionEntry | null>(null);
  const [showInfo, setShowInfo] = useState(false);

  const positions = data?.ip_position?.positions;
  const timeline = useMemo(
    () => buildPatentTimeline(positions ?? [], { includeExpired: showExpired }),
    [positions, showExpired],
  );

  const now = new Date().getFullYear();
  const [minYear, maxYear] = useMemo(() => {
    if (zoom === 'full') return [timeline.minYear, timeline.maxYear];
    const span = zoom === '5y' ? 5 : 10;
    return [now, now + span];
  }, [zoom, timeline.minYear, timeline.maxYear, now]);

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <LoadingSpinner />
      </div>
    );
  }

  if (!data) {
    return (
      <EmptyState
        title="No patent data available"
        description="Run IP analysis first."
        action={
          <Button onClick={() => refetch()} variant="outline">
            <RefreshCw className="mr-2 h-4 w-4" /> Retry
          </Button>
        }
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-2xl font-semibold">Patent White Space Map</h2>
        <div className="flex flex-wrap items-center gap-2">
          {(['5y', '10y', 'full'] as Zoom[]).map((z) => (
            <Button
              key={z}
              size="sm"
              variant={zoom === z ? 'default' : 'outline'}
              onClick={() => setZoom(z)}
            >
              {z === 'full' ? 'Full' : z === '5y' ? '5-yr' : '10-yr'}
            </Button>
          ))}
          <label className="flex items-center gap-1 text-xs">
            <input
              type="checkbox"
              checked={showExpired}
              onChange={(e) => setShowExpired(e.target.checked)}
            />
            Show expired
          </label>
          <Button
            size="sm"
            variant="outline"
            onClick={() => void exportPatentMapPNG()}
          >
            <Download className="mr-1 h-4 w-4" /> PNG
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setShowInfo(true)}>
            <Info className="mr-1 h-4 w-4" /> White space?
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => refetch()}
            disabled={isFetching}
          >
            <RefreshCw className={cn('mr-1 h-4 w-4', isFetching && 'animate-spin')} />
            Refresh
          </Button>
        </div>
      </div>

      {timeline.bars.length === 0 ? (
        <EmptyState
          title="No patents in this window"
          description="Adjust the zoom or toggle 'Show expired' to see more."
        />
      ) : (
        <Card>
          <CardContent className="p-4" id="patent-map-canvas">
            <GanttChart
              timeline={timeline}
              minYear={minYear}
              maxYear={maxYear}
              indFilingYear={indFilingYear}
              onPatentClick={setSelectedPatent}
            />
          </CardContent>
        </Card>
      )}

      <Dialog open={!!selectedPatent} onOpenChange={(o) => !o && setSelectedPatent(null)}>
        <DialogContent>
          {selectedPatent && (
            <>
              <DialogHeader>
                <DialogTitle>
                  {selectedPatent.patent_number ?? 'Patent details'}
                </DialogTitle>
              </DialogHeader>
              <div className="space-y-1 text-sm">
                {selectedPatent.patent_family && (
                  <p>
                    <strong>Family:</strong> {selectedPatent.patent_family}
                  </p>
                )}
                {selectedPatent.assignee && (
                  <p>
                    <strong>Assignee:</strong> {selectedPatent.assignee}
                  </p>
                )}
                {selectedPatent.expiry_year && (
                  <p>
                    <strong>Expiry:</strong> {selectedPatent.expiry_year}
                  </p>
                )}
                {selectedPatent.jurisdiction && (
                  <p>
                    <strong>Jurisdiction:</strong> {selectedPatent.jurisdiction}
                  </p>
                )}
                {selectedPatent.claims && (
                  <p className="text-xs text-muted-foreground">
                    {selectedPatent.claims}
                  </p>
                )}
                {selectedPatent.freedom_to_operate_estimate != null && (
                  <p>
                    <strong>FTO estimate:</strong>{' '}
                    {selectedPatent.freedom_to_operate_estimate.toFixed(2)}
                  </p>
                )}
                {selectedPatent.patent_number && (
                  <a
                    href={`https://patents.google.com/?q=${encodeURIComponent(selectedPatent.patent_number)}`}
                    target="_blank"
                    rel="noreferrer"
                    className="text-primary underline"
                  >
                    View on Google Patents
                  </a>
                )}
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={showInfo} onOpenChange={setShowInfo}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>What is white space?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            A white-space window is a year range in which no blocking patents
            are active. The estimated freedom-to-operate (FTO) is computed from
            the non-blocking patents that overlap the window — higher is safer.
          </p>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ============================================================
// SVG Gantt
// ============================================================

function GanttChart({
  timeline,
  minYear,
  maxYear,
  indFilingYear,
  onPatentClick,
}: {
  timeline: ReturnType<typeof buildPatentTimeline>;
  minYear: number;
  maxYear: number;
  indFilingYear?: number;
  onPatentClick: (p: IPPositionEntry) => void;
}) {
  const years = maxYear - minYear || 1;
  const width = 900;
  const rowHeight = 28;
  const headerHeight = 30;
  const leftAxis = 160;
  const chartWidth = width - leftAxis - 20;
  const height = headerHeight + timeline.assignees.length * rowHeight + 30;
  const yearToX = (y: number) =>
    leftAxis + ((Math.max(minYear, Math.min(maxYear, y)) - minYear) / years) * chartWidth;

  // Year ticks every ~2 years.
  const tickEvery = years <= 10 ? 1 : years <= 20 ? 2 : 5;
  const ticks: number[] = [];
  for (let y = minYear; y <= maxYear; y += tickEvery) ticks.push(y);

  return (
    <div className="overflow-x-auto">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full" role="img">
        {/* White-space windows */}
        {timeline.whiteSpace
          .filter((w) => w.endYear >= minYear && w.startYear <= maxYear)
          .map((w, i) => {
            const x1 = yearToX(w.startYear);
            const x2 = yearToX(w.endYear);
            return (
              <g key={`ws-${i}`}>
                <rect
                  x={x1}
                  y={headerHeight}
                  width={Math.max(2, x2 - x1)}
                  height={timeline.assignees.length * rowHeight}
                  fill="#bbf7d0"
                  fillOpacity={0.35}
                >
                  <title>
                    Freedom to operate: {w.fto} | No blocking patents{' '}
                    {w.startYear}–{w.endYear}
                  </title>
                </rect>
              </g>
            );
          })}

        {/* Axis */}
        <line
          x1={leftAxis}
          x2={width - 20}
          y1={headerHeight}
          y2={headerHeight}
          stroke="hsl(var(--border))"
        />
        {ticks.map((y) => (
          <g key={y}>
            <line
              x1={yearToX(y)}
              x2={yearToX(y)}
              y1={headerHeight}
              y2={height - 20}
              stroke="hsl(var(--border))"
              strokeDasharray="2 4"
              strokeOpacity={0.5}
            />
            <text
              x={yearToX(y)}
              y={headerHeight - 8}
              fontSize={10}
              textAnchor="middle"
              fill="currentColor"
            >
              {y}
            </text>
          </g>
        ))}

        {/* Rows */}
        {timeline.assignees.map((a, i) => (
          <g key={a}>
            <text
              x={10}
              y={headerHeight + i * rowHeight + rowHeight / 2 + 4}
              fontSize={11}
              fill="currentColor"
            >
              {a.length > 22 ? a.slice(0, 22) + '…' : a}
            </text>
            <line
              x1={leftAxis}
              x2={width - 20}
              y1={headerHeight + i * rowHeight + rowHeight}
              y2={headerHeight + i * rowHeight + rowHeight}
              stroke="hsl(var(--border))"
              strokeOpacity={0.3}
            />
          </g>
        ))}

        {/* Bars */}
        {timeline.bars.map((b: PatentBar, i) => {
          const x1 = yearToX(b.filingYear);
          const x2 = yearToX(b.expiryYear);
          const y = headerHeight + b.row * rowHeight + 6;
          const color = b.isBlocking ? '#ef4444' : '#9ca3af';
          return (
            <g key={b.id + i}>
              <rect
                x={x1}
                y={y}
                width={Math.max(3, x2 - x1)}
                height={rowHeight - 12}
                rx={3}
                fill={color}
                fillOpacity={0.85}
                stroke={color}
                style={{ cursor: 'pointer' }}
                onClick={() => onPatentClick(b.patent)}
              >
                <title>
                  {b.patent.patent_number ?? 'Patent'} ({b.filingYear}–{b.expiryYear})
                </title>
              </rect>
              {/* Expiry marker */}
              <line
                x1={x2}
                x2={x2}
                y1={headerHeight}
                y2={height - 20}
                stroke="#ef4444"
                strokeDasharray="3 3"
                strokeOpacity={0.4}
              />
            </g>
          );
        })}

        {/* Candidate IND marker */}
        {indFilingYear && indFilingYear >= minYear && indFilingYear <= maxYear && (
          <g>
            <polygon
              points={`${yearToX(indFilingYear)},${headerHeight + 4} ${yearToX(indFilingYear) + 8},${headerHeight + 14} ${yearToX(indFilingYear)},${headerHeight + 24} ${yearToX(indFilingYear) - 8},${headerHeight + 14}`}
              fill="#8b5cf6"
              stroke="#6d28d9"
            >
              <title>Estimated IND filing: {indFilingYear}</title>
            </polygon>
          </g>
        )}
      </svg>
      <div className="mt-2 flex items-center gap-4 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1">
          <span className="h-3 w-3 rounded-sm bg-red-500" /> Blocking patent
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="h-3 w-3 rounded-sm bg-gray-400" /> Non-blocking
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="h-3 w-3 rounded-sm bg-emerald-200" /> White space
        </span>
        {indFilingYear && (
          <span className="inline-flex items-center gap-1">
            <span className="text-[#8b5cf6]">◆</span> IND filing
          </span>
        )}
      </div>
    </div>
  );
}

/** PNG export via dynamic html2canvas import with graceful fallback. */
async function exportPatentMapPNG(): Promise<void> {
  if (typeof window === 'undefined') return;
  const el = document.getElementById('patent-map-canvas');
  if (!el) return;
  try {
    const dynImport: (m: string) => Promise<unknown> = (m) =>
      (Function('m', 'return import(m)') as (m: string) => Promise<unknown>)(m);
    const mod = (await dynImport('html2canvas').catch(() => null)) as
      | { default?: (el: HTMLElement) => Promise<HTMLCanvasElement> }
      | ((el: HTMLElement) => Promise<HTMLCanvasElement>)
      | null;
    if (!mod) throw new Error('html2canvas not installed');
    const html2canvas =
      typeof mod === 'function' ? mod : mod.default;
    if (!html2canvas) throw new Error('html2canvas not installed');
    const canvas = await html2canvas(el);
    const url = canvas.toDataURL('image/png');
    const a = document.createElement('a');
    a.href = url;
    a.download = 'patent-map.png';
    a.click();
  } catch {
    toast(
      'PNG export requires html2canvas. Use your browser screenshot tool as a fallback.',
    );
  }
}
