'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  type Edge,
  type Node,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { entityColor } from '@/lib/utils/colors';
import type { EvidenceGraph } from '@/lib/types/genovate';

interface EvidenceGraphProps {
  graph: EvidenceGraph;
  onSelectEntity?: (entityId: string) => void;
  search?: string;
}

/**
 * Renders a Genovate evidence graph using React Flow.
 *
 * - Entities are color-coded by `entity_type` (gene/disease/compound/pathway/assay).
 * - Edges scale stroke width/opacity by `confidence`.
 * - Optional `search` argument highlights matching nodes.
 * - Edges that appear after the first render (e.g., delivered via the
 *   `/ws/program/{id}` evidence_edge_added event which triggers a cache
 *   invalidation) pulse for ~3s to draw attention to live updates.
 */
export function EvidenceGraphView({ graph, onSelectEntity, search }: EvidenceGraphProps) {
  const knownEdgeIds = useRef<Set<string>>(new Set());
  const [highlightedEdges, setHighlightedEdges] = useState<Set<string>>(new Set());
  const initialized = useRef(false);

  useEffect(() => {
    const incoming = graph.edges.map((e) => e.id);
    if (!initialized.current) {
      // Seed the known set on first render so we don't flash everything.
      incoming.forEach((id) => knownEdgeIds.current.add(id));
      initialized.current = true;
      return;
    }
    const newOnes = incoming.filter((id) => !knownEdgeIds.current.has(id));
    if (newOnes.length === 0) return;
    newOnes.forEach((id) => knownEdgeIds.current.add(id));
    setHighlightedEdges((prev) => {
      const next = new Set(prev);
      newOnes.forEach((id) => next.add(id));
      return next;
    });
    const timer = setTimeout(() => {
      setHighlightedEdges((prev) => {
        const next = new Set(prev);
        newOnes.forEach((id) => next.delete(id));
        return next;
      });
    }, 3000);
    return () => clearTimeout(timer);
  }, [graph.edges]);

  const { nodes, edges } = useMemo(
    () => buildElements(graph, search, highlightedEdges),
    [graph, search, highlightedEdges],
  );

  return (
    <div className="h-[600px] w-full rounded-lg border bg-card">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        onNodeClick={(_e, n) => onSelectEntity?.(n.id)}
        nodesDraggable
        nodesConnectable={false}
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={16} />
        <MiniMap pannable zoomable className="!bg-background" />
        <Controls />
      </ReactFlow>
    </div>
  );
}

function buildElements(
  graph: EvidenceGraph,
  search: string | undefined,
  highlightedEdges: Set<string>,
): { nodes: Node[]; edges: Edge[] } {
  const lower = search?.trim().toLowerCase();
  const count = Math.max(graph.entities.length, 1);
  const radius = Math.max(200, count * 18);

  const nodes: Node[] = graph.entities.map((entity, idx) => {
    const angle = (idx / count) * Math.PI * 2;
    const color = entityColor(entity.entity_type);
    const isMatch = lower ? entity.name.toLowerCase().includes(lower) : true;

    return {
      id: entity.id,
      position: {
        x: Math.cos(angle) * radius,
        y: Math.sin(angle) * radius,
      },
      data: { label: entity.name },
      style: {
        background: color,
        color: '#fff',
        border: '1px solid rgba(0,0,0,0.1)',
        borderRadius: 8,
        padding: 6,
        fontSize: 12,
        opacity: isMatch ? 1 : 0.25,
      },
    };
  });

  const edges: Edge[] = graph.edges.map((edge) => {
    const isNew = highlightedEdges.has(edge.id);
    return {
      id: edge.id,
      source: edge.source_id,
      target: edge.target_id,
      label: edge.relation,
      animated: isNew || edge.confidence >= 0.75,
      style: {
        strokeWidth: isNew ? 3 : 0.5 + edge.confidence * 3,
        opacity: isNew ? 1 : 0.3 + edge.confidence * 0.7,
        stroke: isNew ? '#22c55e' : undefined,
        filter: isNew ? 'drop-shadow(0 0 6px rgba(34,197,94,0.7))' : undefined,
      },
      labelStyle: { fontSize: 10 },
      className: isNew ? 'evidence-edge--new' : undefined,
    };
  });

  return { nodes, edges };
}
