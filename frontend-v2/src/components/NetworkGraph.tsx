import { useEffect, useRef, useState } from 'react';
import { useChat } from '../contexts/ChatContext';
import { GraphVisualizer } from './GraphVisualizer';
import type { GraphNode, GraphEdge } from './GraphVisualizer';
import { Maximize2, Minimize2, Network, X } from 'lucide-react';

export function NetworkGraph() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const visualizerRef = useRef<GraphVisualizer | null>(null);
  const { activeGraphData } = useChat();
  const [isFullscreen, setIsFullscreen] = useState(false);
  // The clicked node, remembered with the graph it belongs to so a new graph clears it.
  const [selection, setSelection] = useState<{ id: string; graph: unknown } | null>(null);
  const graphRef = useRef(activeGraphData);

  useEffect(() => {
    if (!canvasRef.current) return;
    const visualizer = new GraphVisualizer(canvasRef.current, (node) => setSelection({ id: node.id, graph: graphRef.current }));
    visualizerRef.current = visualizer;
    return () => {
      visualizer.destroy();
      visualizerRef.current = null;
    };
  }, []);

  useEffect(() => {
    graphRef.current = activeGraphData;
    if (!visualizerRef.current || !activeGraphData) return;
    // Copies, because the visualizer mutates nodes/edges while laying them out.
    const nodes: GraphNode[] = activeGraphData.nodes.map((n) => ({ id: n.id, label: n.label, type: n.type }));
    const edges: GraphEdge[] = activeGraphData.edges.map((e) => ({ source: e.source, target: e.target, relation: e.type }));
    visualizerRef.current.setData(nodes, edges);
  }, [activeGraphData]);

  useEffect(() => {
    visualizerRef.current?.resize();
  }, [isFullscreen]);

  // Details for the clicked node, read from the untouched API payload.
  const selectedId = selection?.graph === activeGraphData ? selection.id : null;
  const labelOf = (id: string) => activeGraphData?.nodes.find((n) => n.id === id)?.label ?? id;
  const selected = selectedId ? activeGraphData?.nodes.find((n) => n.id === selectedId) : undefined;
  const links = selectedId
    ? (activeGraphData?.edges ?? [])
        .filter((e) => e.source === selectedId || e.target === selectedId)
        .map((e) => ({ relation: e.type, outgoing: e.source === selectedId, other: labelOf(e.source === selectedId ? e.target : e.source) }))
    : [];

  return (
    <div className={`relative flex flex-col overflow-hidden bg-slate-950 ${isFullscreen ? 'fixed inset-4 z-50 rounded-lg border border-slate-700' : 'h-full w-full'}`}>
      <button
        className="absolute right-3 top-3 z-10 rounded-md border border-slate-700 bg-slate-800 p-1.5 text-slate-300 hover:text-slate-50"
        onClick={() => setIsFullscreen(!isFullscreen)}
        aria-label={isFullscreen ? 'Exit full screen' : 'Full screen'}
      >
        {isFullscreen ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
      </button>

      <div className="relative h-full w-full flex-1">
        <canvas ref={canvasRef} className="absolute inset-0 h-full w-full outline-none" />

        {!activeGraphData && (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center p-6 text-center">
            <div>
              <Network className="mx-auto mb-3 h-10 w-10 text-slate-700" />
              <div className="text-sm text-slate-400">No graph yet</div>
              <div className="text-xs text-slate-500">Ask about a person and the people and emails involved appear here.</div>
            </div>
          </div>
        )}

        {activeGraphData && !selected && (
          <div className="pointer-events-none absolute bottom-3 left-3 text-xs text-slate-500">Click a node for details · drag to move</div>
        )}

        {selected && (
          <div className="absolute bottom-3 left-3 right-3 max-h-[45%] overflow-y-auto rounded-lg border border-slate-700 bg-slate-900/95 p-4 shadow-xl backdrop-blur sm:right-auto sm:w-80">
            <div className="mb-2 flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="text-xs font-mono text-blue-400">{selected.type}</div>
                <div className="break-words text-sm font-medium text-slate-50">{selected.label}</div>
              </div>
              <button onClick={() => setSelection(null)} className="p-0.5 text-slate-400 hover:text-slate-50" aria-label="Close details">
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="mb-1 text-xs text-slate-400">{links.length} connection{links.length === 1 ? '' : 's'}</div>
            <ul className="space-y-1 text-xs">
              {links.map((l, i) => (
                <li key={i} className="flex gap-2 text-slate-300">
                  <span className="shrink-0 font-mono text-slate-500">{l.outgoing ? '→' : '←'} {l.relation}</span>
                  <span className="truncate" title={l.other}>{l.other}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
