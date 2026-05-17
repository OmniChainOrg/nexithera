import { format, formatDistanceToNow, parseISO } from 'date-fns';

export function formatDate(iso: string | null | undefined, pattern = 'PP'): string {
  if (!iso) return '—';
  try {
    return format(parseISO(iso), pattern);
  } catch {
    return iso ?? '—';
  }
}

export function formatDateTime(iso: string | null | undefined): string {
  return formatDate(iso, 'PPp');
}

export function formatRelative(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    return formatDistanceToNow(parseISO(iso), { addSuffix: true });
  } catch {
    return iso ?? '—';
  }
}

export function formatPercent(value: number, fractionDigits = 0): string {
  if (Number.isNaN(value)) return '—';
  return `${(value * 100).toFixed(fractionDigits)}%`;
}

export function formatScore(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return value.toFixed(2);
}

export function titleCase(value: string): string {
  return value
    .split('_')
    .map((part) => (part.length ? part[0].toUpperCase() + part.slice(1) : part))
    .join(' ');
}
