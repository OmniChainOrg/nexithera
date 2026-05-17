'use client';

import { useMemo } from 'react';
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
 */
export function EvidenceGraphView({ graph, onSelectEntity, search }: EvidenceGraphProps) {
  const { nodes, edges } = useMemo(() => buildElements(graph, search), [graph, search]);

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

  const edges: Edge[] = graph.edges.map((edge) => ({
    id: edge.id,
    source: edge.source_id,
    target: edge.target_id,
    label: edge.relation,
    animated: edge.confidence >= 0.75,
    style: {
      strokeWidth: 0.5 + edge.confidence * 3,
      opacity: 0.3 + edge.confidence * 0.7,
    },
    labelStyle: { fontSize: 10 },
  }));

  return { nodes, edges };
}
