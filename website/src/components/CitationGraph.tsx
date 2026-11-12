"use client"

import React, { useEffect, useRef } from 'react';

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
  selectedNodeIds: string[];
  onNodePositionUpdate: (nodeId: string, x: number, y: number) => void;
}

export default function CitationGraph({ nodes, onNodeSelect, selectedNodeIds, onNodePositionUpdate }: CitationGraphProps) {
  return (
    <div className="w-full h-full bg-white border border-neutral-200 rounded-lg overflow-hidden shadow-soft">
      <div className="p-4 border-b border-neutral-100">
        <h3 className="font-medium text-sm">Citation Network</h3>
      </div>
      <div className="relative w-full h-[calc(100%-40px)]">
        {/* graph here */}
        <div className="absolute inset-0 flex items-center justify-center text-neutral-400 text-sm">
          Graph engine placeholder
        </div>
      </div>
    </div>
  );
}