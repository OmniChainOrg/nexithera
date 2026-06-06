import type {
  CompetitorEntry,
  INDReadinessResponse,
  PartnerabilityResponse,
} from '@/lib/api/partnerability';
import { calculateINDProgress } from './ind-progress';
import { sortPartners } from './partner-matchmaker';

export interface BDSummaryDoc {
  title: string;
  generatedAt: string;
  candidate: {
    id: string;
    name?: string;
    phase?: string;
  };
  overall: {
    score: number;
    verdict: string;
    subscores: { label: string; value: number }[];
  };
  topPartners: {
    name: string;
    fitScore: number;
    rationale: string;
  }[];
  indReadiness: {
    percentage: number;
    complete: number;
    total: number;
    estimatedTimelineMonths?: number;
    criticalGaps: string[];
  };
  topThreats: {
    asset: string;
    developer?: string | null;
    phase?: string | null;
    threatLevel?: string | null;
  }[];
}

export interface BDSummaryInput {
  partnerability: PartnerabilityResponse;
  candidateName?: string;
  candidatePhase?: string;
  indReadiness?: INDReadinessResponse | null;
  competitors?: CompetitorEntry[];
  now?: Date;
}

/**
 * Pure function that assembles the structured content for the BD summary
 * PDF. Kept independent of jsPDF so it is easy to test and so the PDF
 * generator can be swapped (e.g. server-side rendering).
 */
export function buildBDSummary(input: BDSummaryInput): BDSummaryDoc {
  const { partnerability: p } = input;
  const now = input.now ?? new Date();

  const partners = sortPartners(p.potential_partners ?? [], 'fit_desc').slice(0, 3);

  const competitors = input.competitors ?? p.competitive_landscape?.competitors ?? [];
  const threatRank: Record<string, number> = { high: 0, medium: 1, low: 2 };
  const topThreats = competitors
    .slice()
    .sort((a, b) => {
      const ra = threatRank[a.threat_level ?? 'low'] ?? 3;
      const rb = threatRank[b.threat_level ?? 'low'] ?? 3;
      return ra - rb;
    })
    .slice(0, 3)
    .map((c) => ({
      asset: c.asset_name,
      developer: c.developer,
      phase: c.phase,
      threatLevel: c.threat_level,
    }));

  const ind = calculateINDProgress(
    input.indReadiness ?? p.ind_readiness_assessment ?? null,
  );

  return {
    title: `BD Partnerability Summary — ${input.candidateName ?? p.candidate_id}`,
    generatedAt: now.toISOString(),
    candidate: {
      id: p.candidate_id,
      name: input.candidateName,
      phase: input.candidatePhase,
    },
    overall: {
      score: Math.round(p.overall_score * 10) / 10,
      verdict: p.verdict,
      subscores: [
        { label: 'Competitive Moat', value: p.competitive_moat },
        { label: 'IP Strength', value: p.ip_strength },
        { label: 'Unmet Need', value: p.unmet_need },
        { label: 'IND Readiness', value: p.ind_readiness },
      ],
    },
    topPartners: partners.map((pa) => ({
      name: pa.name,
      fitScore: pa.fit_score,
      rationale: pa.rationale,
    })),
    indReadiness: {
      percentage: ind.percentage,
      complete: ind.complete,
      total: ind.total,
      estimatedTimelineMonths: ind.estimatedTimelineMonths,
      criticalGaps: ind.criticalGaps.map((g) => g.item),
    },
    topThreats,
  };
}

/** Render a BD summary doc as plain text (used as the PDF fallback body). */
export function bdSummaryToText(doc: BDSummaryDoc): string {
  const lines: string[] = [];
  lines.push(doc.title);
  lines.push(`Generated: ${doc.generatedAt}`);
  lines.push('');
  lines.push(
    `Candidate: ${doc.candidate.name ?? doc.candidate.id}` +
      (doc.candidate.phase ? ` — Phase ${doc.candidate.phase}` : ''),
  );
  lines.push('');
  lines.push(`Overall Partnerability: ${doc.overall.score}/10 (${doc.overall.verdict})`);
  for (const s of doc.overall.subscores) {
    lines.push(`  • ${s.label}: ${s.value.toFixed(1)}`);
  }
  lines.push('');
  lines.push('Top Partners:');
  if (doc.topPartners.length === 0) lines.push('  (none)');
  for (const pa of doc.topPartners) {
    lines.push(`  • ${pa.name} — fit ${pa.fitScore.toFixed(1)}/10`);
    lines.push(`      ${pa.rationale}`);
  }
  lines.push('');
  lines.push(
    `IND Readiness: ${doc.indReadiness.percentage}% (${doc.indReadiness.complete}/${doc.indReadiness.total})` +
      (doc.indReadiness.estimatedTimelineMonths != null
        ? ` — ~${doc.indReadiness.estimatedTimelineMonths} months to IND`
        : ''),
  );
  if (doc.indReadiness.criticalGaps.length) {
    lines.push('  Critical gaps:');
    for (const g of doc.indReadiness.criticalGaps) lines.push(`    • ${g}`);
  }
  lines.push('');
  lines.push('Top Competitive Threats:');
  if (doc.topThreats.length === 0) lines.push('  (none)');
  for (const t of doc.topThreats) {
    lines.push(
      `  • ${t.asset}${t.developer ? ` (${t.developer})` : ''}` +
        `${t.phase ? ` — ${t.phase}` : ''}` +
        `${t.threatLevel ? ` — ${t.threatLevel} threat` : ''}`,
    );
  }
  return lines.join('\n');
}
