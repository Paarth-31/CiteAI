"use client"

import React, { useState, useEffect } from 'react';
import { X, Sparkles } from 'lucide-react';
import ResultCard from './ResultCard';

interface SelectedItem {
  id: string;
  type: 'chunk' | 'node';
  title: string;
}

interface AnalysisWorkspaceProps {
  selectedItems: SelectedItem[];
  onItemDeselect: (id: string) => void;
}

export default function AnalysisWorkspace({ selectedItems, onItemDeselect }: AnalysisWorkspaceProps) {
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<any[]>([]);

  useEffect(() => {
    if (selectedItems.length > 0) {
      handleAnalyze();
    } else {
      setResults([]);
      setLoading(false);
    }
  }, [selectedItems]);

  const handleAnalyze = () => {
    setLoading(true);
    setTimeout(() => {
      const mockResults = [
        {
          id: '1',
          sourceTitle: 'System Architecture Guidelines (2024)',
          metadata: {
            year: 2024,
            sourceType: 'Technical Spec',
            references: 42,
          },
          risk: 'low' as const,
          sentiment: 'positive' as const,
          trs: 92,
          explanation: 'This source provides strong infrastructural support for your query. The documentation aligns closely with the semantic content of your selected chunks.',
          irac: {
            issue: 'Whether the current deployment structure supports zero-downtime scaling.',
            rule: 'According to Section 4.2, load balancers must be configured with health checks prior to traffic routing.',
            application: 'The proposed architecture implements the required health checks and redundant routing.',
            conclusion: 'The system meets the criteria for zero-downtime scaling validation.',
          },
        },
      ];
      
      setResults(mockResults);
      setLoading(false);
    }, 2000);
  };

  const handleFeedback = (resultId: string, feedback: 'up' | 'down') => {
    console.log(`Feedback for result ${resultId}: ${feedback}`);
  };

  return (
    <div className="h-full glass-card rounded-2xl p-6 overflow-hidden flex flex-col">
      <div className="mb-6">
        <h2 className="text-lg font-bold text-[#f0f4f8] flex items-center gap-2 font-[var(--font-heading)]">
          <Sparkles size={20} className="text-[#29b6f6]" />
          Workspace Analysis
        </h2>
        <p className="text-[#6b7a8d] text-xs mt-1.5 font-[var(--font-mono)] tracking-wider uppercase">
          {loading ? 'Processing Insights...' : results.length > 0 ? `${results.length} Output Results` : 'Select context items'}
        </p>
      </div>

      {selectedItems.length === 0 ? (
        <div className="flex-1 flex items-center justify-center border-2 border-dashed border-[#242c3a] rounded-xl bg-[#161b25]/50">
          <div className="text-center text-[#6b7a8d] px-4">
            <Sparkles size={36} className="mx-auto mb-4 opacity-40 text-[#29b6f6]" />
            <p className="text-sm font-medium font-[var(--font-sans)]">No context selected</p>
            <p className="text-xs mt-1 opacity-70">Click nodes in the network to add them here.</p>
          </div>
        </div>
      ) : (
        <div className="flex-1 overflow-hidden flex flex-col">
          {/* Selected Items */}
          <div className="mb-6">
            <h3 className="text-[#6b7a8d] text-xs font-bold mb-3 font-[var(--font-mono)] tracking-widest uppercase">
              Selected Sources ({selectedItems.length})
            </h3>
            <div className="space-y-2 max-h-[150px] overflow-y-auto scrollbar-thin pr-2">
              {selectedItems.map((item) => (
                <div
                  key={item.id}
                  className="bg-[#1e2433] border border-[#242c3a] hover:border-[#29b6f6]/50 rounded-xl p-3 flex items-center justify-between group transition-colors"
                >
                  <div className="flex items-center gap-3 flex-1 min-w-0">
                    <span className="badge-cyan flex-shrink-0">
                      {item.type}
                    </span>
                    <span className="text-[#e8edf2] text-sm font-medium truncate font-[var(--font-sans)]">{item.title}</span>
                  </div>
                  <button
                    onClick={() => onItemDeselect(item.id)}
                    className="text-[#6b7a8d] hover:text-[#f43f5e] transition-colors ml-3 flex-shrink-0 bg-[#161b25] hover:bg-[#f43f5e]/10 p-1.5 rounded-lg"
                  >
                    <X size={14} />
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Loading State */}
          {loading && (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center bg-[#1e2433]/50 p-8 rounded-2xl border border-[#242c3a]">
                <div className="relative h-12 w-12 mx-auto mb-5">
                  <div className="absolute inset-0 rounded-full border-2 border-[#242c3a]"></div>
                  <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-[#29b6f6] animate-spin"></div>
                </div>
                <p className="text-[#e8edf2] text-sm font-bold mb-3 font-[var(--font-heading)]">Synthesizing Data...</p>
                <div className="space-y-2 text-left inline-block">
                  <div className="flex items-center gap-3">
                    <div className="animate-pulse w-2 h-2 bg-[#29b6f6] rounded-full"></div>
                    <span className="text-xs text-[#6b7a8d] font-[var(--font-mono)]">Cross-referencing sources</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="animate-pulse w-2 h-2 bg-[#81d4fa] rounded-full" style={{ animationDelay: '0.2s' }}></div>
                    <span className="text-xs text-[#6b7a8d] font-[var(--font-mono)]">Evaluating logic frameworks</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="animate-pulse w-2 h-2 bg-[#1a6fa3] rounded-full" style={{ animationDelay: '0.4s' }}></div>
                    <span className="text-xs text-[#6b7a8d] font-[var(--font-mono)]">Generating insights</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Results */}
          {!loading && results.length > 0 && (
            <div className="flex-1 overflow-y-auto space-y-4 pr-2 scrollbar-thin">
              <div className="flex items-center justify-between mb-1 pt-2 border-t border-[#242c3a]">
                <h3 className="text-[#6b7a8d] text-xs font-bold font-[var(--font-mono)] tracking-widest uppercase">
                  Analysis Output
                </h3>
                <span className="badge-cyan">
                  Complete
                </span>
              </div>
              {results.map((result) => (
                <ResultCard key={result.id} result={result} onFeedback={handleFeedback} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}