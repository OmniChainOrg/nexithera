'use client';

import { Download } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { qualityToColor } from '@/lib/utils/heatmap';
import type { EvidenceGap } from '@/lib/types/genovate';

export function GapExportButton({ targets, diseases, gaps }: { targets: { id: string; name: string }[]; diseases: { id: string; name: string }[]; gaps: EvidenceGap[] }) {
  function exportPng() {
    const cell = 64;
    const label = 160;
    const canvas = document.createElement('canvas');
    canvas.width = label + diseases.length * cell;
    canvas.height = label + targets.length * cell;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = '#111827';
    ctx.font = '12px sans-serif';
    diseases.forEach((d, i) => ctx.fillText(d.name.slice(0, 16), label + i * cell + 6, 24));
    const byCell = new Map(gaps.map((g) => [`${g.target_id}:${g.disease_id}`, g]));
    targets.forEach((t, y) => {
      ctx.fillStyle = '#111827';
      ctx.fillText(t.name.slice(0, 22), 8, label + y * cell + 34);
      diseases.forEach((d, x) => {
        const g = byCell.get(`${t.id}:${d.id}`);
        ctx.fillStyle = qualityToColor(g?.evidence_quality ?? 0);
        ctx.fillRect(label + x * cell, label + y * cell, cell, cell);
        ctx.strokeStyle = '#ffffff';
        ctx.strokeRect(label + x * cell, label + y * cell, cell, cell);
        ctx.fillStyle = '#111827';
        ctx.fillText(g ? g.evidence_quality.toFixed(2) : '—', label + x * cell + 18, label + y * cell + 36);
      });
    });
    const link = document.createElement('a');
    link.download = 'gap-heatmap.png';
    link.href = canvas.toDataURL('image/png');
    link.click();
  }
  return <Button variant="outline" onClick={exportPng}><Download className="h-4 w-4" />Export PNG</Button>;
}
