// "use client"

// import React, { useState, useEffect, useRef } from 'react';
// import { ZoomIn, ZoomOut, RotateCcw, Move, MousePointer } from 'lucide-react';

// interface CitationNode {
//   id: string;
//   title: string;
//   x: number;
//   y: number;
//   citations: number;
//   year: number;
// }

// interface CitationGraphProps {
//   nodes: CitationNode[];
//   edges: { source: string; target: string }[];   
//   onNodeSelect: (node: CitationNode) => void;
//   selectedNodeIds?: string[];
//   onNodePositionUpdate?: (nodeId: string, x: number, y: number) => void;
// }

// export default function CitationGraph({ nodes: initialNodes, edges, onNodeSelect, selectedNodeIds = [], onNodePositionUpdate }: CitationGraphProps) {
//   const [zoom, setZoom] = useState(1);
//   const [hoveredNode, setHoveredNode] = useState<string | null>(null);
//   const [nodes, setNodes] = useState(initialNodes);
//   const [draggedNode, setDraggedNode] = useState<string | null>(null);
//   const [isDragging, setIsDragging] = useState(false);
//   const [interactionMode, setInteractionMode] = useState<'pointer' | 'pan'>('pointer');
//   const [panOffset, setPanOffset] = useState({ x: 0, y: 0 });
//   const [isPanning, setIsPanning] = useState(false);
//   const containerRef = useRef<HTMLDivElement>(null);
//   const dragStartPos = useRef({ x: 0, y: 0 });
//   const nodeStartPos = useRef({ x: 0, y: 0 });
//   const panStartPos = useRef({ x: 0, y: 0 });

//   useEffect(() => {
//     setNodes(initialNodes);
//   }, [initialNodes]);

//   useEffect(() => {
//     if (isDragging || isPanning) {
//       document.body.style.userSelect = 'none';
//       document.body.style.cursor = isPanning ? 'grabbing' : isDragging ? 'grabbing' : '';
//     } else {
//       document.body.style.userSelect = '';
//       document.body.style.cursor = '';
//     }
//     return () => {
//       document.body.style.userSelect = '';
//       document.body.style.cursor = '';
//     };
//   }, [isDragging, isPanning]);

//   const handleZoomIn = () => setZoom(Math.min(zoom + 0.2, 2));
//   const handleZoomOut = () => setZoom(Math.max(zoom - 0.2, 0.5));
//   const handleRecenter = () => {
//     setZoom(1);
//     setPanOffset({ x: 0, y: 0 });
//     setNodes(initialNodes);
//   };

//   const toggleInteractionMode = () => {
//     setInteractionMode(prev => prev === 'pointer' ? 'pan' : 'pointer');
//   };

//   const handlePointerDown = (e: React.PointerEvent, nodeId?: string) => {
//     e.stopPropagation();
//     e.preventDefault();
    
//     if (interactionMode === 'pan' || !nodeId) {
//       panStartPos.current = { x: e.clientX - panOffset.x, y: e.clientY - panOffset.y };
//       setIsPanning(true);
//       (e.target as HTMLElement).setPointerCapture(e.pointerId);
//     } else {
//       const node = nodes.find(n => n.id === nodeId);
//       if (!node || !containerRef.current) return;

//       dragStartPos.current = { x: e.clientX, y: e.clientY };
//       nodeStartPos.current = { x: node.x, y: node.y };
      
//       setDraggedNode(nodeId);
//       setIsDragging(true);
//       setHoveredNode(null);

//       (e.target as HTMLElement).setPointerCapture(e.pointerId);
//     }
//   };

//   const handlePointerMove = (e: React.PointerEvent) => {
//     if (isPanning) {
//       setPanOffset({
//         x: e.clientX - panStartPos.current.x,
//         y: e.clientY - panStartPos.current.y
//       });
//     } else if (isDragging && draggedNode && containerRef.current) {
//       const rect = containerRef.current.getBoundingClientRect();
      
//       const deltaX = e.clientX - dragStartPos.current.x;
//       const deltaY = e.clientY - dragStartPos.current.y;
      
//       const deltaXPercent = (deltaX / rect.width) * 100;
//       const deltaYPercent = (deltaY / rect.height) * 100;
      
//       let newX = nodeStartPos.current.x + deltaXPercent;
//       let newY = nodeStartPos.current.y + deltaYPercent;
      
//       newX = Math.max(8, Math.min(92, newX));
//       newY = Math.max(8, Math.min(92, newY));
      
//       setNodes(prevNodes =>
//         prevNodes.map(node =>
//           node.id === draggedNode
//             ? { ...node, x: newX, y: newY }
//             : node
//         )
//       );
//     }
//   };

//   const handlePointerUp = (e: React.PointerEvent) => {
//     if (isDragging && draggedNode && onNodePositionUpdate) {
//       const node = nodes.find(n => n.id === draggedNode);
//       if (node) {
//         onNodePositionUpdate(draggedNode, node.x, node.y);
//       }
//     }
    
//     if (isDragging || isPanning) {
//       e.stopPropagation();
//       (e.target as HTMLElement).releasePointerCapture(e.pointerId);
//     }
//     setDraggedNode(null);
//     setIsDragging(false);
//     setIsPanning(false);
//   };

//   const handleNodeClick = (e: React.MouseEvent, node: CitationNode) => {
//     if (!isDragging && !isPanning && interactionMode === 'pointer') {
//       e.stopPropagation();
//       onNodeSelect(node);
//     }
//   };

//   const getNodeSize = (citations: number) => {
//     const minSize = 16;
//     const maxSize = 34;
//     const minCitations = Math.min(...nodes.map(n => n.citations));
//     const maxCitations = Math.max(...nodes.map(n => n.citations));
//     const range = maxCitations - minCitations || 1;
//     return minSize + ((citations - minCitations) / range) * (maxSize - minSize);
//   };

//   return (
//     <div className="h-full bg-transparent rounded-xl p-4 overflow-hidden flex flex-col border-none">
//       <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between mb-4 gap-3 px-2">
//         <div className="flex-1 min-w-0">
//           <h2 className="text-lg font-bold text-[#f0f4f8] truncate font-[var(--font-heading)] tracking-tight">
//             Knowledge Graph Map
//           </h2>
//           <p className="text-[#6b7a8d] text-[11px] mt-1 font-[var(--font-mono)] uppercase tracking-widest hidden sm:block">
//             {interactionMode === 'pointer' ? 'Drag nodes • Click to select' : 'Pan mode active'}
//           </p>
//         </div>
//         <div className="flex items-center gap-2 flex-shrink-0 bg-[#0f1117] p-1.5 rounded-xl border border-[#242c3a] shadow-inner">
//           <button
//             onClick={toggleInteractionMode}
//             className={`p-2 rounded-lg transition-all ${
//               interactionMode === 'pointer'
//                 ? 'bg-[#29b6f6] text-[#050a0e] shadow-[0_0_12px_rgba(41,182,246,0.3)]'
//                 : 'bg-transparent text-[#6b7a8d] hover:bg-[#1e2433] hover:text-[#f0f4f8]'
//             }`}
//             title={interactionMode === 'pointer' ? 'Switch to Pan' : 'Switch to Pointer'}
//           >
//             {interactionMode === 'pointer' ? <MousePointer size={16} /> : <Move size={16} />}
//           </button>
//           <div className="w-px h-6 bg-[#242c3a]"></div>
//           <button
//             onClick={handleZoomOut}
//             className="p-2 bg-transparent hover:bg-[#1e2433] text-[#6b7a8d] hover:text-[#f0f4f8] rounded-lg transition-colors"
//             title="Zoom Out"
//           >
//             <ZoomOut size={16} />
//           </button>
//           <button
//             onClick={handleZoomIn}
//             className="p-2 bg-transparent hover:bg-[#1e2433] text-[#6b7a8d] hover:text-[#f0f4f8] rounded-lg transition-colors"
//             title="Zoom In"
//           >
//             <ZoomIn size={16} />
//           </button>
//           <div className="w-px h-6 bg-[#242c3a]"></div>
//           <button
//             onClick={handleRecenter}
//             className="p-2 bg-transparent hover:bg-[#1e2433] text-[#6b7a8d] hover:text-[#f0f4f8] rounded-lg transition-colors"
//             title="Recenter"
//           >
//             <RotateCcw size={16} />
//           </button>
//         </div>
//       </div>

//       <div 
//         ref={containerRef}
//         className={`flex-1 relative bg-gradient-to-b from-[#0a0a0a] to-[#0f1117] rounded-xl overflow-hidden touch-none border border-[#242c3a] shadow-inner ${
//           interactionMode === 'pan' ? 'cursor-grab' : ''
//         } ${isPanning ? 'cursor-grabbing' : ''}`}
//         onPointerMove={handlePointerMove}
//         onPointerUp={handlePointerUp}
//         onPointerLeave={handlePointerUp}
//         onPointerDown={(e) => interactionMode === 'pan' && handlePointerDown(e)}
//       >
//         {/* Ambient Map Glow */}
//         <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(41,182,246,0.05)_0%,transparent_70%)] pointer-events-none"></div>

//         {/* Axes Labels */}
//         <div className="absolute top-4 left-1/2 -translate-x-1/2 text-[#29b6f6] text-[10px] font-bold font-[var(--font-mono)] tracking-widest uppercase bg-[#161b25]/80 backdrop-blur px-4 py-1.5 rounded-full z-10 pointer-events-none border border-[#29b6f6]/20">
//           <span className="hidden sm:inline">Recent sources →</span>
//           <span className="sm:hidden">Recent →</span>
//         </div>
//         <div className="absolute left-4 top-1/2 -translate-y-1/2 -rotate-90 text-[#29b6f6] text-[10px] font-bold font-[var(--font-mono)] tracking-widest uppercase bg-[#161b25]/80 backdrop-blur px-4 py-1.5 rounded-full z-10 pointer-events-none whitespace-nowrap border border-[#29b6f6]/20">
//           <span className="hidden sm:inline">More references →</span>
//           <span className="sm:hidden">Refs →</span>
//         </div>

//         {/* Graph Content */}
//         <div 
//           className="absolute inset-0 flex items-center justify-center transition-transform duration-200"
//           style={{ 
//             transform: `scale(${zoom}) translate(${panOffset.x / zoom}px, ${panOffset.y / zoom}px)`
//           }}
//         >
//           <svg className="w-full h-full overflow-visible">
//             <defs>
//               <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
//                 <feGaussianBlur stdDeviation="4" result="blur" />
//                 <feComposite in="SourceGraphic" in2="blur" operator="over" />
//               </filter>
//             </defs>

//             {/* Crosshair Grid lines */}
//             <line x1="0" y1="50%" x2="100%" y2="50%" stroke="#1e2433" strokeWidth="1" strokeDasharray="4 4" />
//             <line x1="50%" y1="0" x2="50%" y2="100%" stroke="#1e2433" strokeWidth="1" strokeDasharray="4 4" />

//             {/* Connection lines */}
//             {edges.map((edge, i) => {
//               const source = nodes.find(n => n.id === edge.source);
//               const target = nodes.find(n => n.id === edge.target);
//               if (!source || !target) return null;
//               return (
//                 <line
//                   key={`edge-${i}`}
//                   x1={`${source.x}%`} y1={`${source.y}%`}
//                   x2={`${target.x}%`} y2={`${target.y}%`}
//                   stroke="#242c3a" strokeWidth="1.5" strokeDasharray="4 6" opacity="0.7"
//                 />
//               );
//             })}

//             {/* Nodes */}
//             {nodes.map((node) => {
//               const nodeSize = getNodeSize(node.citations);
//               const isSelected = selectedNodeIds.includes(node.id);
//               const isActive = hoveredNode === node.id || draggedNode === node.id;
              
//               return (
//                 <g key={node.id}>
//                   {/* Outer pulse/ring for selected nodes */}
//                   {isSelected && (
//                     <circle
//                       cx={`${node.x}%`}
//                       cy={`${node.y}%`}
//                       r={nodeSize + 8}
//                       fill="none"
//                       stroke="#29b6f6"
//                       strokeWidth="2"
//                       className="transition-all duration-300 opacity-60"
//                       filter="url(#glow)"
//                     />
//                   )}
                  
//                   {/* Main node circle */}
//                   <circle
//                     cx={`${node.x}%`}
//                     cy={`${node.y}%`}
//                     r={nodeSize}
//                     fill={isSelected ? "#29b6f6" : isActive ? "#1a6fa3" : "#161b25"}
//                     stroke={isSelected ? "#29b6f6" : isActive ? "#29b6f6" : "#242c3a"}
//                     strokeWidth="2.5"
//                     className="transition-all duration-200"
//                     style={{ 
//                       cursor: interactionMode === 'pointer' 
//                         ? (draggedNode === node.id ? 'grabbing' : 'grab')
//                         : 'default',
//                     }}
//                     onPointerEnter={() => !isDragging && !isPanning && setHoveredNode(node.id)}
//                     onPointerLeave={() => !isDragging && !isPanning && setHoveredNode(null)}
//                     onPointerDown={(e) => interactionMode === 'pointer' && handlePointerDown(e as any, node.id)}
//                     onClick={(e) => handleNodeClick(e as any, node)}
//                   />
                  
//                   {/* Citation count */}
//                   <text
//                     x={`${node.x}%`}
//                     y={`${node.y}%`}
//                     textAnchor="middle"
//                     dominantBaseline="central"
//                     className="text-[12px] font-bold font-[var(--font-mono)] pointer-events-none select-none"
//                     fill={isSelected ? "#050a0e" : "#f0f4f8"}
//                     style={{ transform: `translateY(1px)` }}
//                   >
//                     {node.citations}
//                   </text>
//                 </g>
//               );
//             })}
//           </svg>

//           {/* Tooltips */}
//           {nodes.map((node) => (
//             hoveredNode === node.id && !isDragging && !isPanning && (
//               <div
//                 key={`tooltip-${node.id}`}
//                 className="absolute bg-[#0f1117]/95 backdrop-blur-md border border-[#242c3a] rounded-xl p-3.5 pointer-events-none z-20 shadow-[0_8px_32px_rgba(0,0,0,0.8)]"
//                 style={{
//                   left: `${node.x}%`,
//                   top: `${node.y}%`,
//                   transform: 'translate(-50%, calc(-100% - 20px))',
//                   maxWidth: '220px',
//                   minWidth: '160px',
//                 }}
//               >
//                 <p className="text-[#f0f4f8] font-bold text-sm mb-2 leading-snug font-[var(--font-sans)]">{node.title}</p>
//                 <div className="flex items-center justify-between border-t border-[#242c3a] pt-2 mt-1">
//                   <span className="text-[10px] text-[#29b6f6] font-[var(--font-mono)] uppercase tracking-wider font-bold">{node.citations} Refs</span>
//                   <span className="text-[10px] text-[#6b7a8d] font-[var(--font-mono)]">{node.year}</span>
//                 </div>
//               </div>
//             )
//           ))}
//         </div>
//       </div>
//     </div>
//   );
// }


"use client"

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { ZoomIn, ZoomOut, RotateCcw, MousePointer, Move } from 'lucide-react';

interface CitationNode {
  id: string;
  title: string;
  x: number;
  y: number;
  citations: number;
  year: number;
}

interface CitationGraphProps {
  nodes: CitationNode[];
  edges: { source: string; target: string }[];
  onNodeSelect: (node: CitationNode) => void;
  selectedNodeIds?: string[];
  onNodePositionUpdate?: (nodeId: string, x: number, y: number) => void;
}

// Force-directed layout computed entirely in the browser
function computeLayout(rawNodes: CitationNode[], edges: { source: string; target: string }[]): CitationNode[] {
  if (rawNodes.length === 0) return [];
  if (rawNodes.length === 1) return [{ ...rawNodes[0], x: 50, y: 50 }];

  // Build citation count from edges (how many times each node is cited)
  const citedBy: Record<string, number> = {};
  edges.forEach(e => { citedBy[e.target] = (citedBy[e.target] || 0) + 1; });

  // The node with the most outgoing edges is the central "root" document
  const outgoing: Record<string, number> = {};
  edges.forEach(e => { outgoing[e.source] = (outgoing[e.source] || 0) + 1; });
  const rootId = Object.entries(outgoing).sort((a, b) => b[1] - a[1])[0]?.[0] ?? rawNodes[0].id;

  // Assign relevance score: root = 1.0, direct refs = 0.7, others by citations
  const maxCited = Math.max(1, ...Object.values(citedBy));
  const relevance: Record<string, number> = {};
  rawNodes.forEach(n => {
    if (n.id === rootId) { relevance[n.id] = 1.0; return; }
    const isDirectRef = edges.some(e => e.source === rootId && e.target === n.id);
    if (isDirectRef) { relevance[n.id] = 0.65 + 0.2 * ((citedBy[n.id] || 0) / maxCited); }
    else { relevance[n.id] = 0.1 + 0.4 * ((citedBy[n.id] || 0) / maxCited); }
  });

  // Initialize positions: root at center, others on concentric rings by relevance
  const positions: Record<string, { x: number; y: number }> = {};
  const cx = 50, cy = 50;

  const groups = {
    root: rawNodes.filter(n => n.id === rootId),
    direct: rawNodes.filter(n => n.id !== rootId && relevance[n.id] >= 0.65),
    secondary: rawNodes.filter(n => n.id !== rootId && relevance[n.id] < 0.65 && relevance[n.id] >= 0.3),
    peripheral: rawNodes.filter(n => n.id !== rootId && relevance[n.id] < 0.3),
  };

  // Place root at center
  groups.root.forEach(n => { positions[n.id] = { x: cx, y: cy }; });

  // Direct refs on inner ring (radius ~22%)
  groups.direct.forEach((n, i) => {
    const angle = (2 * Math.PI * i) / Math.max(1, groups.direct.length) - Math.PI / 2;
    positions[n.id] = { x: cx + 22 * Math.cos(angle), y: cy + 22 * Math.sin(angle) };
  });

  // Secondary on middle ring (radius ~35%)
  groups.secondary.forEach((n, i) => {
    const angle = (2 * Math.PI * i) / Math.max(1, groups.secondary.length) - Math.PI / 4;
    positions[n.id] = { x: cx + 35 * Math.cos(angle), y: cy + 35 * Math.sin(angle) };
  });

  // Peripheral on outer ring (radius ~44%)
  groups.peripheral.forEach((n, i) => {
    const angle = (2 * Math.PI * i) / Math.max(1, groups.peripheral.length);
    positions[n.id] = { x: cx + 44 * Math.cos(angle), y: cy + 44 * Math.sin(angle) };
  });

  // Run force-directed simulation to de-overlap
  const pos = rawNodes.map(n => ({ id: n.id, x: positions[n.id]?.x ?? cx, y: positions[n.id]?.y ?? cy }));
  const edgeSet = new Set(edges.map(e => `${e.source}:${e.target}`));

  for (let iter = 0; iter < 120; iter++) {
    const forces: Record<string, { fx: number; fy: number }> = {};
    pos.forEach(n => { forces[n.id] = { fx: 0, fy: 0 }; });

    // Repulsion between all nodes
    for (let i = 0; i < pos.length; i++) {
      for (let j = i + 1; j < pos.length; j++) {
        const a = pos[i], b = pos[j];
        const dx = a.x - b.x, dy = a.y - b.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 0.01;
        const repulse = 180 / (dist * dist);
        const fx = (dx / dist) * repulse, fy = (dy / dist) * repulse;
        forces[a.id].fx += fx; forces[a.id].fy += fy;
        forces[b.id].fx -= fx; forces[b.id].fy -= fy;
      }
    }

    // Attraction along edges
    edges.forEach(e => {
      const src = pos.find(n => n.id === e.source);
      const tgt = pos.find(n => n.id === e.target);
      if (!src || !tgt) return;
      const dx = tgt.x - src.x, dy = tgt.y - src.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 0.01;
      const idealDist = e.source === rootId ? 22 : 30;
      const attract = (dist - idealDist) * 0.04;
      const fx = (dx / dist) * attract, fy = (dy / dist) * attract;
      if (src.id !== rootId) { forces[src.id].fx += fx; forces[src.id].fy += fy; }
      if (tgt.id !== rootId) { forces[tgt.id].fx -= fx; forces[tgt.id].fy -= fy; }
    });

    // Gravity toward center (by relevance — high relevance = strong gravity)
    pos.forEach(n => {
      if (n.id === rootId) return;
      const rel = relevance[n.id] ?? 0.3;
      const dx = cx - n.x, dy = cy - n.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const g = 0.008 * (1 - rel + 0.2);
      forces[n.id].fx += dx * g;
      forces[n.id].fy += dy * g;
    });

    // Apply forces (damped)
    const damping = 0.85;
    pos.forEach(n => {
      if (n.id === rootId) return;
      n.x = Math.max(8, Math.min(92, n.x + forces[n.id].fx * damping));
      n.y = Math.max(8, Math.min(92, n.y + forces[n.id].fy * damping));
    });
  }

  return rawNodes.map(n => {
    const p = pos.find(p => p.id === n.id);
    return { ...n, x: p?.x ?? cx, y: p?.y ?? cy, citations: citedBy[n.id] || n.citations };
  });
}

export default function CitationGraph({ nodes: initialNodes, edges, onNodeSelect, selectedNodeIds = [], onNodePositionUpdate }: CitationGraphProps) {
  const [zoom, setZoom] = useState(1);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [nodes, setNodes] = useState<CitationNode[]>([]);
  const [rootId, setRootId] = useState<string | null>(null);
  const [draggedNode, setDraggedNode] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [interactionMode, setInteractionMode] = useState<'pointer' | 'pan'>('pointer');
  const [panOffset, setPanOffset] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const dragStartPos = useRef({ x: 0, y: 0 });
  const nodeStartPos = useRef({ x: 0, y: 0 });
  const panStartPos = useRef({ x: 0, y: 0 });

  useEffect(() => {
    if (initialNodes.length === 0) { setNodes([]); return; }
    const laid = computeLayout(initialNodes, edges);
    setNodes(laid);
    // Find root: node with most outgoing edges
    const outgoing: Record<string, number> = {};
    edges.forEach(e => { outgoing[e.source] = (outgoing[e.source] || 0) + 1; });
    const root = Object.entries(outgoing).sort((a, b) => b[1] - a[1])[0]?.[0] ?? initialNodes[0].id;
    setRootId(root);
  }, [initialNodes, edges]);

  useEffect(() => {
    document.body.style.userSelect = isDragging || isPanning ? 'none' : '';
    return () => { document.body.style.userSelect = ''; };
  }, [isDragging, isPanning]);

  const handleZoomIn = () => setZoom(z => Math.min(z + 0.2, 3));
  const handleZoomOut = () => setZoom(z => Math.max(z - 0.2, 0.4));
  const handleRecenter = () => {
    setZoom(1); setPanOffset({ x: 0, y: 0 });
    setNodes(computeLayout(initialNodes, edges));
  };

  const handlePointerDown = (e: React.PointerEvent, nodeId?: string) => {
    e.stopPropagation(); e.preventDefault();
    if (interactionMode === 'pan' || !nodeId) {
      panStartPos.current = { x: e.clientX - panOffset.x, y: e.clientY - panOffset.y };
      setIsPanning(true);
    } else {
      const node = nodes.find(n => n.id === nodeId);
      if (!node || !containerRef.current) return;
      dragStartPos.current = { x: e.clientX, y: e.clientY };
      nodeStartPos.current = { x: node.x, y: node.y };
      setDraggedNode(nodeId); setIsDragging(true);
    }
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  };

  const handlePointerMove = (e: React.PointerEvent) => {
    if (isPanning) {
      setPanOffset({ x: e.clientX - panStartPos.current.x, y: e.clientY - panStartPos.current.y });
    } else if (isDragging && draggedNode && containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      const dxP = ((e.clientX - dragStartPos.current.x) / rect.width) * 100;
      const dyP = ((e.clientY - dragStartPos.current.y) / rect.height) * 100;
      setNodes(prev => prev.map(n => n.id === draggedNode
        ? { ...n, x: Math.max(5, Math.min(95, nodeStartPos.current.x + dxP)), y: Math.max(5, Math.min(95, nodeStartPos.current.y + dyP)) }
        : n));
    }
  };

  const handlePointerUp = (e: React.PointerEvent) => {
    if (isDragging && draggedNode && onNodePositionUpdate) {
      const node = nodes.find(n => n.id === draggedNode);
      if (node) onNodePositionUpdate(draggedNode, node.x, node.y);
    }
    (e.target as HTMLElement).releasePointerCapture(e.pointerId);
    setDraggedNode(null); setIsDragging(false); setIsPanning(false);
  };

  const handleNodeClick = (e: React.MouseEvent, node: CitationNode) => {
    if (!isDragging && !isPanning && interactionMode === 'pointer') {
      e.stopPropagation(); onNodeSelect(node);
    }
  };

  // Node size: root is large, others scale by citations
  const getNodeSize = useCallback((node: CitationNode) => {
    if (node.id === rootId) return 30;
    const maxC = Math.max(1, ...nodes.filter(n => n.id !== rootId).map(n => n.citations));
    const minSize = 12, maxSize = 24;
    return minSize + (node.citations / maxC) * (maxSize - minSize);
  }, [nodes, rootId]);

  // Node color by ring
  const getNodeColor = (node: CitationNode, isSelected: boolean, isActive: boolean) => {
    if (isSelected) return { fill: '#29b6f6', stroke: '#29b6f6', text: '#050a0e' };
    if (node.id === rootId) return { fill: '#1a6fa3', stroke: '#29b6f6', text: '#f0f4f8' };
    if (isActive) return { fill: '#1e2d3d', stroke: '#29b6f6', text: '#f0f4f8' };
    // color by citation count
    if (node.citations >= 3) return { fill: '#1a2535', stroke: '#3b82f6', text: '#93c5fd' };
    if (node.citations >= 1) return { fill: '#161b25', stroke: '#334155', text: '#c9d1dc' };
    return { fill: '#0f1117', stroke: '#242c3a', text: '#6b7a8d' };
  };

  if (nodes.length === 0) {
    return (
      <div className="h-full bg-transparent rounded-xl p-4 flex flex-col border-none">
        <div className="flex items-center justify-between mb-4 px-2">
          <div>
            <h2 className="text-lg font-bold text-[#f0f4f8] font-[var(--font-heading)]">Knowledge Graph Map</h2>
            <p className="text-[#6b7a8d] text-[11px] mt-1 font-[var(--font-mono)] uppercase tracking-widest">Upload a document to begin</p>
          </div>
        </div>
        <div className="flex-1 flex items-center justify-center bg-gradient-to-b from-[#0a0a0a] to-[#0f1117] rounded-xl border border-[#242c3a]">
          <div className="text-center">
            <div className="w-16 h-16 rounded-full border-2 border-dashed border-[#242c3a] flex items-center justify-center mx-auto mb-4">
              <span className="text-2xl opacity-30">⬡</span>
            </div>
            <p className="text-[#6b7a8d] text-sm font-[var(--font-sans)]">No citation graph yet</p>
            <p className="text-[#3d4a5c] text-xs mt-1 font-[var(--font-mono)]">Upload a PDF to generate the graph</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full bg-transparent rounded-xl p-4 overflow-hidden flex flex-col border-none">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between mb-4 gap-3 px-2">
        <div className="flex-1 min-w-0">
          <h2 className="text-lg font-bold text-[#f0f4f8] truncate font-[var(--font-heading)] tracking-tight">Knowledge Graph Map</h2>
          <p className="text-[#6b7a8d] text-[11px] mt-1 font-[var(--font-mono)] uppercase tracking-widest hidden sm:block">
            {interactionMode === 'pointer' ? 'Drag nodes • Click to select' : 'Pan mode active'} • {nodes.length} nodes
          </p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0 bg-[#0f1117] p-1.5 rounded-xl border border-[#242c3a] shadow-inner">
          <button onClick={() => setInteractionMode(m => m === 'pointer' ? 'pan' : 'pointer')}
            className={`p-2 rounded-lg transition-all ${interactionMode === 'pointer' ? 'bg-[#29b6f6] text-[#050a0e] shadow-[0_0_12px_rgba(41,182,246,0.3)]' : 'bg-transparent text-[#6b7a8d] hover:bg-[#1e2433] hover:text-[#f0f4f8]'}`}
            title={interactionMode === 'pointer' ? 'Switch to Pan' : 'Switch to Pointer'}>
            {interactionMode === 'pointer' ? <MousePointer size={16} /> : <Move size={16} />}
          </button>
          <div className="w-px h-6 bg-[#242c3a]" />
          <button onClick={handleZoomOut} className="p-2 hover:bg-[#1e2433] text-[#6b7a8d] hover:text-[#f0f4f8] rounded-lg transition-colors" title="Zoom Out"><ZoomOut size={16} /></button>
          <button onClick={handleZoomIn} className="p-2 hover:bg-[#1e2433] text-[#6b7a8d] hover:text-[#f0f4f8] rounded-lg transition-colors" title="Zoom In"><ZoomIn size={16} /></button>
          <div className="w-px h-6 bg-[#242c3a]" />
          <button onClick={handleRecenter} className="p-2 hover:bg-[#1e2433] text-[#6b7a8d] hover:text-[#f0f4f8] rounded-lg transition-colors" title="Recenter"><RotateCcw size={16} /></button>
        </div>
      </div>

      {/* Canvas */}
      <div
        ref={containerRef}
        className={`flex-1 relative bg-gradient-to-b from-[#070a0f] to-[#0f1117] rounded-xl overflow-hidden touch-none border border-[#1a2030] shadow-inner ${interactionMode === 'pan' ? 'cursor-grab' : ''} ${isPanning ? '!cursor-grabbing' : ''}`}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerLeave={handlePointerUp}
        onPointerDown={(e) => interactionMode === 'pan' && handlePointerDown(e)}
      >
        {/* Radial glow at center */}
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_60%_50%_at_50%_50%,rgba(41,182,246,0.06)_0%,transparent_70%)] pointer-events-none" />

        {/* Legend */}
        <div className="absolute bottom-3 right-3 z-10 pointer-events-none flex flex-col gap-1.5 bg-[#0b0e15]/80 backdrop-blur border border-[#1a2030] rounded-xl p-3">
          <p className="text-[9px] font-[var(--font-mono)] text-[#3d4a5c] uppercase tracking-widest mb-0.5">Proximity = Relevance</p>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded-full bg-[#1a6fa3] border-2 border-[#29b6f6]" />
            <span className="text-[9px] text-[#6b7a8d] font-[var(--font-mono)]">Root document</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-[#1a2535] border border-[#3b82f6]" />
            <span className="text-[9px] text-[#6b7a8d] font-[var(--font-mono)]">Frequently cited</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full bg-[#0f1117] border border-[#242c3a]" />
            <span className="text-[9px] text-[#6b7a8d] font-[var(--font-mono)]">Peripheral source</span>
          </div>
        </div>

        <div
          className="absolute inset-0"
          style={{ transform: `scale(${zoom}) translate(${panOffset.x / zoom}px, ${panOffset.y / zoom}px)`, transformOrigin: 'center center', transition: isDragging || isPanning ? 'none' : 'transform 0.15s ease' }}
        >
          <svg className="w-full h-full overflow-visible">
            <defs>
              <filter id="glow-strong"><feGaussianBlur stdDeviation="5" result="blur" /><feComposite in="SourceGraphic" in2="blur" operator="over" /></filter>
              <filter id="glow-soft"><feGaussianBlur stdDeviation="2.5" result="blur" /><feComposite in="SourceGraphic" in2="blur" operator="over" /></filter>
              <marker id="arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
                <path d="M0,0 L0,6 L6,3 z" fill="#29b6f6" opacity="0.4" />
              </marker>
            </defs>

            {/* Concentric reference rings */}
            {[22, 35, 44].map((r, i) => (
              <ellipse key={r} cx="50%" cy="50%" rx={`${r}%`} ry={`${r * 0.85}%`}
                fill="none" stroke="#1a2030" strokeWidth="1" strokeDasharray={i === 0 ? '3 5' : '2 8'} opacity={0.5 - i * 0.12} />
            ))}

            {/* Edges — directed arrows */}
            {edges.map((edge, i) => {
              const src = nodes.find(n => n.id === edge.source);
              const tgt = nodes.find(n => n.id === edge.target);
              if (!src || !tgt) return null;
              const isRootEdge = edge.source === rootId || edge.target === rootId;
              return (
                <line key={`e-${i}`}
                  x1={`${src.x}%`} y1={`${src.y}%`}
                  x2={`${tgt.x}%`} y2={`${tgt.y}%`}
                  stroke={isRootEdge ? '#29b6f6' : '#2a3545'}
                  strokeWidth={isRootEdge ? 1.5 : 1}
                  strokeDasharray={isRootEdge ? 'none' : '3 7'}
                  opacity={isRootEdge ? 0.35 : 0.25}
                  markerEnd={isRootEdge ? 'url(#arrow)' : undefined}
                />
              );
            })}

            {/* Nodes */}
            {nodes.map((node) => {
              const size = getNodeSize(node);
              const isSelected = selectedNodeIds.includes(node.id);
              const isActive = hoveredNode === node.id || draggedNode === node.id;
              const isRoot = node.id === rootId;
              const colors = getNodeColor(node, isSelected, isActive);

              return (
                <g key={node.id}>
                  {/* Pulse ring for root node */}
                  {isRoot && (
                    <circle cx={`${node.x}%`} cy={`${node.y}%`} r={size + 10}
                      fill="none" stroke="#29b6f6" strokeWidth="1.5" opacity="0.2" filter="url(#glow-soft)" />
                  )}
                  {/* Selected ring */}
                  {isSelected && (
                    <circle cx={`${node.x}%`} cy={`${node.y}%`} r={size + 7}
                      fill="none" stroke="#29b6f6" strokeWidth="2" opacity="0.5" filter="url(#glow-soft)" />
                  )}
                  {/* Hover glow */}
                  {isActive && !isSelected && (
                    <circle cx={`${node.x}%`} cy={`${node.y}%`} r={size + 4}
                      fill="none" stroke="#29b6f6" strokeWidth="1" opacity="0.3" />
                  )}
                  {/* Main circle */}
                  <circle
                    cx={`${node.x}%`} cy={`${node.y}%`} r={size}
                    fill={colors.fill} stroke={colors.stroke} strokeWidth={isRoot ? 2.5 : 1.5}
                    className="transition-all duration-150"
                    style={{ cursor: interactionMode === 'pointer' ? (draggedNode === node.id ? 'grabbing' : 'grab') : 'default', filter: isRoot ? 'url(#glow-soft)' : undefined }}
                    onPointerEnter={() => !isDragging && !isPanning && setHoveredNode(node.id)}
                    onPointerLeave={() => !isDragging && !isPanning && setHoveredNode(null)}
                    onPointerDown={(e) => interactionMode === 'pointer' && handlePointerDown(e as any, node.id)}
                    onClick={(e) => handleNodeClick(e as any, node)}
                  />
                  {/* Label: citation count for small nodes, short title for root */}
                  {isRoot ? (
                    <text x={`${node.x}%`} y={`${node.y}%`} textAnchor="middle" dominantBaseline="central"
                      fontSize="9" fontWeight="bold" fill={colors.text} className="pointer-events-none select-none"
                      style={{ fontFamily: 'var(--font-mono)' }}>
                      ROOT
                    </text>
                  ) : (
                    <text x={`${node.x}%`} y={`${node.y}%`} textAnchor="middle" dominantBaseline="central"
                      fontSize={size > 18 ? "11" : "9"} fontWeight="bold" fill={colors.text}
                      className="pointer-events-none select-none" style={{ fontFamily: 'var(--font-mono)' }}>
                      {node.citations}
                    </text>
                  )}
                </g>
              );
            })}
          </svg>

          {/* Tooltips */}
          {nodes.map(node => hoveredNode === node.id && !isDragging && !isPanning && (
            <div key={`tt-${node.id}`}
              className="absolute bg-[#0b0e15]/98 backdrop-blur-md border border-[#242c3a] rounded-xl p-3.5 pointer-events-none z-30 shadow-[0_8px_32px_rgba(0,0,0,0.9)]"
              style={{ left: `${node.x}%`, top: `${node.y}%`, transform: 'translate(-50%, calc(-100% - 18px))', maxWidth: '240px', minWidth: '170px' }}>
              {node.id === rootId && (
                <div className="text-[9px] font-[var(--font-mono)] text-[#29b6f6] uppercase tracking-widest mb-1.5 font-bold">● Root Document</div>
              )}
              <p className="text-[#f0f4f8] font-bold text-sm mb-2 leading-snug font-[var(--font-sans)]">{node.title}</p>
              <div className="flex items-center justify-between border-t border-[#1e2433] pt-2">
                <span className="text-[10px] text-[#29b6f6] font-[var(--font-mono)] font-bold uppercase tracking-wider">{node.citations} citations</span>
                {node.year > 0 && <span className="text-[10px] text-[#6b7a8d] font-[var(--font-mono)]">{node.year}</span>}
              </div>
              <p className="text-[9px] text-[#3d4a5c] font-[var(--font-mono)] mt-1.5">Click to add to workspace</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}