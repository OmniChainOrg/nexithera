import type { IPPositionEntry } from '@/lib/api/partnerability';

export interface PatentBar {
  id: string;
  patent: IPPositionEntry;
  assignee: string;
  filingYear: number;
  expiryYear: number;
  isBlocking: boolean;
  /** Row index after grouping by assignee, used for Y placement. */
  row: number;
}

export interface WhiteSpaceWindow {
  startYear: number;
  endYear: number;
  /** Estimated freedom-to-operate (0..1) based on overlapping non-blocking patents. */
  fto: number;
}

export interface PatentTimeline {
  bars: PatentBar[];
  /** Distinct assignees in display order. */
  assignees: string[];
  whiteSpace: WhiteSpaceWindow[];
  minYear: number;
  maxYear: number;
}

const DEFAULT_FILING_LOOKBACK_YEARS = 20;
const DEFAULT_TIMELINE_MIN = 2024;
const DEFAULT_TIMELINE_MAX = 2040;

/**
 * When a patent does not carry a filing year (the API only guarantees
 * `expiry_year`), assume a 20-year term — the statutory US/EP default.
 */
function inferFilingYear(p: IPPositionEntry): number {
  if (p.expiry_year != null) {
    return p.expiry_year - DEFAULT_FILING_LOOKBACK_YEARS;
  }
  return DEFAULT_TIMELINE_MIN;
}

/**
 * Build the Gantt-style data structure used by `<PatentMap />`.
 *
 * @param positions  Patents from the partnerability response.
 * @param options.includeExpired  When false (default), patents whose expiry
 *                                is strictly before `options.now` are dropped.
 * @param options.now             Current year for expiry filtering. Defaults
 *                                to the system year.
 * @param options.range           Optional [min,max] override for the X-axis.
 */
export function buildPatentTimeline(
  positions: IPPositionEntry[] | null | undefined,
  options: {
    includeExpired?: boolean;
    now?: number;
    range?: [number, number];
  } = {},
): PatentTimeline {
  const includeExpired = options.includeExpired ?? false;
  const now = options.now ?? new Date().getFullYear();

  const filtered = (positions ?? []).filter((p) => {
    if (includeExpired) return true;
    return p.expiry_year == null || p.expiry_year >= now;
  });

  // Stable assignee order: first appearance.
  const assignees: string[] = [];
  const rowByAssignee = new Map<string, number>();
  for (const p of filtered) {
    const a = p.assignee?.trim() || 'Unknown';
    if (!rowByAssignee.has(a)) {
      rowByAssignee.set(a, assignees.length);
      assignees.push(a);
    }
  }

  const bars: PatentBar[] = filtered.map((p, idx) => {
    const assignee = p.assignee?.trim() || 'Unknown';
    const filingYear = inferFilingYear(p);
    const expiryYear = p.expiry_year ?? DEFAULT_TIMELINE_MAX;
    return {
      id: p.id ?? p.patent_number ?? `patent-${idx}`,
      patent: p,
      assignee,
      filingYear,
      expiryYear,
      isBlocking: !!p.is_blocking,
      row: rowByAssignee.get(assignee) ?? 0,
    };
  });

  const [minYear, maxYear] =
    options.range ?? computeRange(bars, now);

  const whiteSpace = computeWhiteSpace(bars, minYear, maxYear);

  return { bars, assignees, whiteSpace, minYear, maxYear };
}

function computeRange(bars: PatentBar[], now: number): [number, number] {
  if (bars.length === 0) {
    return [DEFAULT_TIMELINE_MIN, DEFAULT_TIMELINE_MAX];
  }
  const min = Math.min(DEFAULT_TIMELINE_MIN, now, ...bars.map((b) => b.filingYear));
  const max = Math.max(DEFAULT_TIMELINE_MAX, ...bars.map((b) => b.expiryYear));
  return [min, max];
}

/**
 * White space = contiguous year ranges in which *no blocking patent* is
 * active. FTO is approximated by the mean of (1 - blocking_fraction) over
 * the window using overlapping non-blocking FTO estimates when available.
 */
export function computeWhiteSpace(
  bars: PatentBar[],
  minYear: number,
  maxYear: number,
): WhiteSpaceWindow[] {
  if (maxYear < minYear) return [];

  const blocking = bars.filter((b) => b.isBlocking);
  const windows: WhiteSpaceWindow[] = [];
  let windowStart: number | null = minYear;

  for (let y = minYear; y <= maxYear; y++) {
    const blockedHere = blocking.some(
      (b) => y >= b.filingYear && y <= b.expiryYear,
    );
    if (blockedHere) {
      if (windowStart != null && y - 1 >= windowStart) {
        windows.push(makeWindow(bars, windowStart, y - 1));
      }
      windowStart = null;
    } else if (windowStart == null) {
      windowStart = y;
    }
  }
  if (windowStart != null) {
    windows.push(makeWindow(bars, windowStart, maxYear));
  }
  return windows;
}

function makeWindow(
  bars: PatentBar[],
  startYear: number,
  endYear: number,
): WhiteSpaceWindow {
  const overlapping = bars.filter(
    (b) =>
      !b.isBlocking &&
      b.filingYear <= endYear &&
      b.expiryYear >= startYear &&
      b.patent.freedom_to_operate_estimate != null,
  );
  const fto =
    overlapping.length > 0
      ? overlapping.reduce(
          (acc, b) => acc + (b.patent.freedom_to_operate_estimate ?? 0),
          0,
        ) / overlapping.length
      : 0.9;
  return { startYear, endYear, fto: Math.round(fto * 100) / 100 };
}
