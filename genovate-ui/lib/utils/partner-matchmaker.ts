import type { PotentialPartner } from '@/lib/api/partnerability';

export type PartnerSort = 'fit_desc' | 'alphabetical' | 'strategic';

export interface PartnerFilter {
  /** Inclusive minimum fit score (0–10). */
  minFitScore?: number;
  /** Case-insensitive substring search across company name. */
  search?: string;
}

export function filterPartners(
  partners: PotentialPartner[],
  filter: PartnerFilter = {},
): PotentialPartner[] {
  const search = filter.search?.trim().toLowerCase();
  const min = filter.minFitScore ?? 0;
  return partners.filter((p) => {
    if (p.fit_score < min) return false;
    if (search && !p.name.toLowerCase().includes(search)) return false;
    return true;
  });
}

export function sortPartners(
  partners: PotentialPartner[],
  sort: PartnerSort,
): PotentialPartner[] {
  const out = partners.slice();
  switch (sort) {
    case 'alphabetical':
      out.sort((a, b) => a.name.localeCompare(b.name));
      break;
    case 'strategic':
      // Strategic = focus overlap weighted on top of fit score.
      out.sort((a, b) => {
        const sa = (a.focus_overlap ? 1 : 0) + a.fit_score / 10;
        const sb = (b.focus_overlap ? 1 : 0) + b.fit_score / 10;
        return sb - sa;
      });
      break;
    case 'fit_desc':
    default:
      out.sort((a, b) => b.fit_score - a.fit_score);
      break;
  }
  return out;
}

export function fitScoreColor(score: number): {
  text: string;
  bg: string;
  band: 'low' | 'moderate' | 'high';
} {
  if (score >= 7) return { text: 'text-emerald-600', bg: 'bg-emerald-100', band: 'high' };
  if (score >= 4) return { text: 'text-amber-600', bg: 'bg-amber-100', band: 'moderate' };
  return { text: 'text-red-600', bg: 'bg-red-100', band: 'low' };
}

export function initialsFor(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() ?? '')
    .join('');
}

// ---------- Shortlist (localStorage stub) -------------------------------

const SHORTLIST_KEY = 'partner_shortlist';

export function getShortlist(): string[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(SHORTLIST_KEY);
    return raw ? (JSON.parse(raw) as string[]) : [];
  } catch {
    return [];
  }
}

export function toggleShortlist(name: string): string[] {
  if (typeof window === 'undefined') return [];
  const current = new Set(getShortlist());
  if (current.has(name)) current.delete(name);
  else current.add(name);
  const next = Array.from(current);
  try {
    window.localStorage.setItem(SHORTLIST_KEY, JSON.stringify(next));
  } catch {
    /* ignore quota errors */
  }
  return next;
}
