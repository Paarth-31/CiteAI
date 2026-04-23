"use client"

import React, { useState, useEffect, useRef } from 'react';
import { ZoomIn, ZoomOut, RotateCcw, Move, MousePointer } from 'lucide-react';

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
  onNodeSelect: (node: CitationNode) => void;
  selectedNodeIds?: string[];
  onNodePositionUpdate?: (nodeId: string, x: number, y: number) => void;
}

export default function CitationGraph({ nodes: initialNodes, onNodeSelect, selectedNodeIds = [], onNodePositionUpdate }: CitationGraphProps) {
  const [zoom, setZoom] = useState(1);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [nodes, setNodes] = useState(initialNodes);
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
    setNodes(initialNodes);
  }, [initialNodes]);

  useEffect(() => {
    if (isDragging || isPanning) {
      document.body.style.userSelect = 'none';
      document.body.style.cursor = isPanning ? 'grabbing' : isDragging ? 'grabbing' : '';
    } else {
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
    }
    return () => {
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
    };
  }, [isDragging, isPanning]);

  const handleZoomIn = () => setZoom(Math.min(zoom + 0.2, 2));
  const handleZoomOut = () => setZoom(Math.max(zoom - 0.2, 0.5));
  const handleRecenter = () => {
    setZoom(1);
    setPanOffset({ x: 0, y: 0 });
    setNodes(initialNodes);
  };

  const toggleInteractionMode = () => {
    setInteractionMode(prev => prev === 'pointer' ? 'pan' : 'pointer');
  };

  const handlePointerDown = (e: React.PointerEvent, nodeId?: string) => {
    e.stopPropagation();
    e.preventDefault();
    
    if (interactionMode === 'pan' || !nodeId) {
      panStartPos.current = { x: e.clientX - panOffset.x, y: e.clientY - panOffset.y };
      setIsPanning(true);
      (e.target as HTMLElement).setPointerCapture(e.pointerId);
    } else {
      const node = nodes.find(n => n.id === nodeId);
      if (!node || !containerRef.current) return;

      dragStartPos.current = { x: e.clientX, y: e.clientY };
      nodeStartPos.current = { x: node.x, y: node.y };
      
      setDraggedNode(nodeId);
      setIsDragging(true);
      setHoveredNode(null);

      (e.target as HTMLElement).setPointerCapture(e.pointerId);
    }
  };

  const handlePointerMove = (e: React.PointerEvent) => {
    if (isPanning) {
      setPanOffset({
        x: e.clientX - panStartPos.current.x,
        y: e.clientY - panStartPos.current.y
      });
    } else if (isDragging && draggedNode && containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      
      const deltaX = e.clientX - dragStartPos.current.x;
      const deltaY = e.clientY - dragStartPos.current.y;
      
      const deltaXPercent = (deltaX / rect.width) * 100;
      const deltaYPercent = (deltaY / rect.height) * 100;
      
      let newX = nodeStartPos.current.x + deltaXPercent;
      let newY = nodeStartPos.current.y + deltaYPercent;
      
      newX = Math.max(8, Math.min(92, newX));
      newY = Math.max(8, Math.min(92, newY));
      
      setNodes(prevNodes =>
        prevNodes.map(node =>
          node.id === draggedNode
            ? { ...node, x: newX, y: newY }
            : node
        )
      );
    }
  };

  const handlePointerUp = (e: React.PointerEvent) => {
    if (isDragging && draggedNode && onNodePositionUpdate) {
      const node = nodes.find(n => n.id === draggedNode);
      if (node) {
        onNodePositionUpdate(draggedNode, node.x, node.y);
      }
    }
    
    if (isDragging || isPanning) {
      e.stopPropagation();
      (e.target as HTMLElement).releasePointerCapture(e.pointerId);
    }
    setDraggedNode(null);
    setIsDragging(false);
    setIsPanning(false);
  };

  const handleNodeClick = (e: React.MouseEvent, node: CitationNode) => {
    if (!isDragging && !isPanning && interactionMode === 'pointer') {
      e.stopPropagation();
      onNodeSelect(node);
    }
  };

  const getNodeSize = (citations: number) => {
    const minSize = 16;
    const maxSize = 34;
    const minCitations = Math.min(...nodes.map(n => n.citations));
    const maxCitations = Math.max(...nodes.map(n => n.citations));
    const range = maxCitations - minCitations || 1;
    return minSize + ((citations - minCitations) / range) * (maxSize - minSize);
  };

  return (
    <div className="h-full bg-transparent rounded-xl p-4 overflow-hidden flex flex-col border-none">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between mb-4 gap-3 px-2">
        <div className="flex-1 min-w-0">
          <h2 className="text-lg font-bold text-[#f0f4f8] truncate font-[var(--font-heading)] tracking-tight">
            Knowledge Graph Map
          </h2>
          <p className="text-[#6b7a8d] text-[11px] mt-1 font-[var(--font-mono)] uppercase tracking-widest hidden sm:block">
            {interactionMode === 'pointer' ? 'Drag nodes • Click to select' : 'Pan mode active'}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0 bg-[#0f1117] p-1.5 rounded-xl border border-[#242c3a] shadow-inner">
          <button
            onClick={toggleInteractionMode}
            className={`p-2 rounded-lg transition-all ${
              interactionMode === 'pointer'
                ? 'bg-[#29b6f6] text-[#050a0e] shadow-[0_0_12px_rgba(41,182,246,0.3)]'
                : 'bg-transparent text-[#6b7a8d] hover:bg-[#1e2433] hover:text-[#f0f4f8]'
            }`}
            title={interactionMode === 'pointer' ? 'Switch to Pan' : 'Switch to Pointer'}
          >
            {interactionMode === 'pointer' ? <MousePointer size={16} /> : <Move size={16} />}
          </button>
          <div className="w-px h-6 bg-[#242c3a]"></div>
          <button
            onClick={handleZoomOut}
            className="p-2 bg-transparent hover:bg-[#1e2433] text-[#6b7a8d] hover:text-[#f0f4f8] rounded-lg transition-colors"
            title="Zoom Out"
          >
            <ZoomOut size={16} />
          </button>
          <button
            onClick={handleZoomIn}
            className="p-2 bg-transparent hover:bg-[#1e2433] text-[#6b7a8d] hover:text-[#f0f4f8] rounded-lg transition-colors"
            title="Zoom In"
          >
            <ZoomIn size={16} />
          </button>
          <div className="w-px h-6 bg-[#242c3a]"></div>
          <button
            onClick={handleRecenter}
            className="p-2 bg-transparent hover:bg-[#1e2433] text-[#6b7a8d] hover:text-[#f0f4f8] rounded-lg transition-colors"
            title="Recenter"
          >
            <RotateCcw size={16} />
          </button>
        </div>
      </div>

      <div 
        ref={containerRef}
        className={`flex-1 relative bg-gradient-to-b from-[#0a0a0a] to-[#0f1117] rounded-xl overflow-hidden touch-none border border-[#242c3a] shadow-inner ${
          interactionMode === 'pan' ? 'cursor-grab' : ''
        } ${isPanning ? 'cursor-grabbing' : ''}`}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerLeave={handlePointerUp}
        onPointerDown={(e) => interactionMode === 'pan' && handlePointerDown(e)}
      >
        {/* Ambient Map Glow */}
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(41,182,246,0.05)_0%,transparent_70%)] pointer-events-none"></div>

        {/* Axes Labels */}
        <div className="absolute top-4 left-1/2 -translate-x-1/2 text-[#29b6f6] text-[10px] font-bold font-[var(--font-mono)] tracking-widest uppercase bg-[#161b25]/80 backdrop-blur px-4 py-1.5 rounded-full z-10 pointer-events-none border border-[#29b6f6]/20">
          <span className="hidden sm:inline">Recent sources →</span>
          <span className="sm:hidden">Recent →</span>
        </div>
        <div className="absolute left-4 top-1/2 -translate-y-1/2 -rotate-90 text-[#29b6f6] text-[10px] font-bold font-[var(--font-mono)] tracking-widest uppercase bg-[#161b25]/80 backdrop-blur px-4 py-1.5 rounded-full z-10 pointer-events-none whitespace-nowrap border border-[#29b6f6]/20">
          <span className="hidden sm:inline">More references →</span>
          <span className="sm:hidden">Refs →</span>
        </div>

        {/* Graph Content */}
        <div 
          className="absolute inset-0 flex items-center justify-center transition-transform duration-200"
          style={{ 
            transform: `scale(${zoom}) translate(${panOffset.x / zoom}px, ${panOffset.y / zoom}px)`
          }}
        >
          <svg className="w-full h-full overflow-visible">
            <defs>
              <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="4" result="blur" />
                <feComposite in="SourceGraphic" in2="blur" operator="over" />
              </filter>
            </defs>

            {/* Crosshair Grid lines */}
            <line x1="0" y1="50%" x2="100%" y2="50%" stroke="#1e2433" strokeWidth="1" strokeDasharray="4 4" />
            <line x1="50%" y1="0" x2="50%" y2="100%" stroke="#1e2433" strokeWidth="1" strokeDasharray="4 4" />

            {/* Connection lines */}
            {nodes.slice(0, -1).map((node, i) => {
              const nextNode = nodes[i + 1];
              return (
                <line
                  key={`line-${node.id}`}
                  x1={`${node.x}%`}
                  y1={`${node.y}%`}
                  x2={`${nextNode.x}%`}
                  y2={`${nextNode.y}%`}
                  stroke="#242c3a"
                  strokeWidth="1.5"
                  strokeDasharray="4 6"
                  opacity="0.7"
                />
              );
            })}

            {/* Nodes */}
            {nodes.map((node) => {
              const nodeSize = getNodeSize(node.citations);
              const isSelected = selectedNodeIds.includes(node.id);
              const isActive = hoveredNode === node.id || draggedNode === node.id;
              
              return (
                <g key={node.id}>
                  {/* Outer pulse/ring for selected nodes */}
                  {isSelected && (
                    <circle
                      cx={`${node.x}%`}
                      cy={`${node.y}%`}
                      r={nodeSize + 8}
                      fill="none"
                      stroke="#29b6f6"
                      strokeWidth="2"
                      className="transition-all duration-300 opacity-60"
                      filter="url(#glow)"
                    />
                  )}
                  
                  {/* Main node circle */}
                  <circle
                    cx={`${node.x}%`}
                    cy={`${node.y}%`}
                    r={nodeSize}
                    fill={isSelected ? "#29b6f6" : isActive ? "#1a6fa3" : "#161b25"}
                    stroke={isSelected ? "#29b6f6" : isActive ? "#29b6f6" : "#242c3a"}
                    strokeWidth="2.5"
                    className="transition-all duration-200"
                    style={{ 
                      cursor: interactionMode === 'pointer' 
                        ? (draggedNode === node.id ? 'grabbing' : 'grab')
                        : 'default',
                    }}
                    onPointerEnter={() => !isDragging && !isPanning && setHoveredNode(node.id)}
                    onPointerLeave={() => !isDragging && !isPanning && setHoveredNode(null)}
                    onPointerDown={(e) => interactionMode === 'pointer' && handlePointerDown(e as any, node.id)}
                    onClick={(e) => handleNodeClick(e as any, node)}
                  />
                  
                  {/* Citation count */}
                  <text
                    x={`${node.x}%`}
                    y={`${node.y}%`}
                    textAnchor="middle"
                    dominantBaseline="central"
                    className="text-[12px] font-bold font-[var(--font-mono)] pointer-events-none select-none"
                    fill={isSelected ? "#050a0e" : "#f0f4f8"}
                    style={{ transform: `translateY(1px)` }}
                  >
                    {node.citations}
                  </text>
                </g>
              );
            })}
          </svg>

          {/* Tooltips */}
          {nodes.map((node) => (
            hoveredNode === node.id && !isDragging && !isPanning && (
              <div
                key={`tooltip-${node.id}`}
                className="absolute bg-[#0f1117]/95 backdrop-blur-md border border-[#242c3a] rounded-xl p-3.5 pointer-events-none z-20 shadow-[0_8px_32px_rgba(0,0,0,0.8)]"
                style={{
                  left: `${node.x}%`,
                  top: `${node.y}%`,
                  transform: 'translate(-50%, calc(-100% - 20px))',
                  maxWidth: '220px',
                  minWidth: '160px',
                }}
              >
                <p className="text-[#f0f4f8] font-bold text-sm mb-2 leading-snug font-[var(--font-sans)]">{node.title}</p>
                <div className="flex items-center justify-between border-t border-[#242c3a] pt-2 mt-1">
                  <span className="text-[10px] text-[#29b6f6] font-[var(--font-mono)] uppercase tracking-wider font-bold">{node.citations} Refs</span>
                  <span className="text-[10px] text-[#6b7a8d] font-[var(--font-mono)]">{node.year}</span>
                </div>
              </div>
            )
          ))}
        </div>
      </div>
    </div>
  );
}