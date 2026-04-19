"use client"

import React from 'react';

export default function CitationGraph({ data }: { data: any }) {
  if (!data) return null;

  return (
    <div className="w-full h-full min-h-[400px] bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
      <h3 className="font-semibold text-lg border-b pb-3 mb-4">Citation Network Results</h3>
      
      <div className="grid grid-cols-2 gap-6">
        <div>
          <h4 className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-2">Detected Nodes</h4>
          <ul className="space-y-2">
            {data.nodes.map((node: any) => (
              <li key={node.id} className="bg-gray-50 px-3 py-2 rounded border border-gray-100 text-sm flex justify-between">
                <span>{node.title}</span>
                <span className="text-green-600 font-medium">{node.citations} refs</span>
              </li>
            ))}
          </ul>
        </div>
        
        <div>
          <h4 className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-2">Detected Edges</h4>
          <ul className="space-y-2">
            {data.edges.map((edge: any, i: number) => (
              <li key={i} className="bg-gray-50 px-3 py-2 rounded border border-gray-100 text-sm text-gray-600">
                Node {edge.source} $\rightarrow$ Node {edge.target}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}