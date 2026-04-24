"use client";

import React, { useEffect, useState, useRef } from 'react';
import { fetchExternalInference, ExternalInferenceResponse, ExternalInferenceResultCase } from '@/lib/api';
import { useToast } from './ToastProvider';
import { BarChart2, RefreshCcw, X, Info } from 'lucide-react';

interface Props {
  documentId: string | null;
}

export default function ExternalInferencePanel({ documentId }: Props) {
  const { showToast } = useToast();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<ExternalInferenceResponse | null>(null);
  const [expandedCaseId, setExpandedCaseId] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const [topK, setTopK] = useState(5);
  const [showFactors, setShowFactors] = useState(false);

  useEffect(() => {
    if (!documentId) {
      setData(null); setError(null); setLoading(false); return;
    }
    runInference();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [documentId]);

  const runInference = () => {
    if (!documentId) return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    setError(null);
    showToast({ message: 'Executing global source indexing…', variant: 'info' });
    fetchExternalInference(documentId, { topK, factors: showFactors, signal: controller.signal })
      .then(resp => {
        setData(resp);
        showToast({ message: 'Global mapping complete', variant: 'success' });
      })
      .catch(err => {
        if (controller.signal.aborted) return;
        console.error('External inference failed', err);
        setError(err.message || 'Failed to execute global search protocol');
        showToast({ message: 'Global mapping failed', variant: 'error' });
      })
      .finally(() => setLoading(false));
  };

  const overall = data?.overall_external_coherence_score ?? 0;
  const scoreBadgeColor = overall >= 0.7 ? 'bg-[rgba(41,182,246,0.15)] text-[#29b6f6] border border-[#29b6f6]/40' 
                        : overall >= 0.5 ? 'bg-amber-500/15 text-amber-400 border border-amber-500/40' 
                        : 'bg-[#f43f5e]/15 text-[#f43f5e] border border-[#f43f5e]/40';

  return (
    <div className="h-full glass-card rounded-2xl p-6 flex flex-col">
      <div className="flex items-start justify-between mb-5">
        <div>
          <h2 className="text-xl font-bold text-[#f0f4f8] flex items-center gap-3 font-[var(--font-heading)]">
            <div className="bg-[#29b6f6]/10 p-1.5 rounded-lg border border-[#29b6f6]/30 text-[#29b6f6]">
              <BarChart2 size={20} />
            </div>
            Global Data Validation
          </h2>
          <p className="text-[#6b7a8d] text-xs mt-2 font-[var(--font-mono)] tracking-wide uppercase">Cross-referencing global database parameters.</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => runInference()}
            disabled={loading || !documentId}
            className="btn-secondary text-[11px] px-3 py-1.5 border-[#242c3a] bg-[#161b25] disabled:opacity-50 disabled:cursor-not-allowed"
            title="Refresh Analysis"
          >
            {loading ? <span className="inline-block h-3.5 w-3.5 border-2 border-[#6b7a8d] border-t-[#29b6f6] rounded-full animate-spin" /> : <RefreshCcw size={14} />}
            SYNC
          </button>
        </div>
      </div>

      {/* Controls */}
      <div className="mb-5 flex flex-wrap gap-3 items-center bg-[#161b25] p-3 rounded-xl border border-[#242c3a]">
        <div className="flex items-center gap-2">
          <label className="text-[10px] text-[#c9d1dc] font-bold font-[var(--font-mono)] tracking-widest uppercase">Depth</label>
          <input
            type="number"
            min={1}
            max={15}
            value={topK}
            onChange={e => setTopK(Math.min(15, Math.max(1, parseInt(e.target.value || '5', 10))))}
            className="w-16 text-xs px-3 py-1.5 border border-[#242c3a] rounded-lg bg-[#0f1117] text-[#f0f4f8] focus:border-[#29b6f6] outline-none text-center font-[var(--font-mono)]"
          />
          <button
            onClick={() => runInference()}
            disabled={loading}
            className="text-[11px] px-3 py-1.5 rounded-lg bg-[#1e2433] text-[#f0f4f8] hover:bg-[#242c3a] font-bold font-[var(--font-mono)] uppercase tracking-wider disabled:opacity-50 transition-colors"
          >Apply</button>
        </div>
        <label className="flex items-center gap-2 text-[11px] text-[#c9d1dc] font-bold font-[var(--font-mono)] tracking-widest uppercase ml-3 cursor-pointer">
          <input
            type="checkbox"
            checked={showFactors}
            onChange={e => setShowFactors(e.target.checked)}
            className="w-4 h-4 rounded bg-[#0f1117] border-[#242c3a] text-[#29b6f6] focus:ring-[#29b6f6]"
          /> 
          Show Vectors
        </label>
        {data && (
          <div className={`text-[11px] ml-auto px-3 py-1.5 rounded-lg font-bold font-[var(--font-mono)] tracking-wider uppercase ${scoreBadgeColor}`}>Index Score: {(overall * 100).toFixed(1)}%</div>
        )}
        {loading && (
          <div className="flex items-center gap-2 text-[#29b6f6] ml-auto bg-[#29b6f6]/10 px-3 py-1.5 rounded-lg border border-[#29b6f6]/20">
            <span className="inline-block h-3.5 w-3.5 border-2 border-[#29b6f6]/30 border-t-[#29b6f6] rounded-full animate-spin" />
            <span className="text-[10px] font-bold font-[var(--font-mono)] tracking-widest uppercase">Indexing...</span>
          </div>
        )}
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto pr-2 scrollbar-thin">
        {!documentId && (
          <div className="text-center text-[#6b7a8d] text-xs py-10 font-[var(--font-mono)] tracking-widest uppercase">Awaiting source document selection...</div>
        )}
        {error && (
          <div className="mb-4 bg-[#f43f5e]/10 border border-[#f43f5e]/20 text-[#f43f5e] text-sm p-4 rounded-xl flex items-start gap-3">
            <X size={18} className="mt-0.5 shrink-0" />
            <span className="font-medium font-[var(--font-sans)]">{error}</span>
          </div>
        )}
        {data && data.retrieved_cases.length === 0 && !error && (
          <div className="text-center text-[#6b7a8d] text-xs py-10 font-[var(--font-mono)] tracking-widest uppercase">0 matches found in global index.</div>
        )}
        {data && data.retrieved_cases.length > 0 && (
          <ul className="space-y-4">
            {data.retrieved_cases.map(c => {
              const trsValue = typeof c.trs === 'number' ? c.trs : c.trs.score;
              const barColor = trsValue >= 0.7 ? 'bg-[#29b6f6] text-[#050a0e]' : trsValue >= 0.5 ? 'bg-amber-400 text-[#050a0e]' : 'bg-[#f43f5e] text-white';
              return (
                <li key={c.case_id} className="bg-[#161b25] border border-[#242c3a] rounded-xl p-4 transition-colors hover:border-[#1a6fa3] shadow-sm">
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0 flex-1">
                      <div className="font-bold text-[#f0f4f8] text-base truncate font-[var(--font-heading)]" title={c.title}>{c.title}</div>
                      <div className="mt-3 flex flex-wrap gap-2 items-center font-[var(--font-mono)]">
                        <div className="flex items-center gap-1.5 bg-[#0f1117] border border-[#242c3a] p-1 rounded-md">
                          <span className="text-[#6b7a8d] text-[10px] font-bold px-1 tracking-widest">IDX:</span>
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${barColor}`}>{(trsValue*100).toFixed(1)}%</span>
                        </div>
                        <span className="text-[#c9d1dc] text-[10px] bg-[#1e2433] px-2 py-1 rounded-md border border-[#242c3a]">SIM {(c.similarity_score*100).toFixed(0)}%</span>
                        <span className="text-[#c9d1dc] text-[10px] bg-[#1e2433] px-2 py-1 rounded-md border border-[#242c3a]">CTX {(c.context_fit*100).toFixed(0)}%</span>
                        <span className="text-[#c9d1dc] text-[10px] bg-[#1e2433] px-2 py-1 rounded-md border border-[#242c3a]">J {(c.jurisdiction_score*100).toFixed(0)}%</span>
                        
                        <button
                          onClick={() => setExpandedCaseId(expandedCaseId === c.case_id ? null : c.case_id)}
                          className="text-[#29b6f6] hover:text-[#f0f4f8] ml-auto text-[11px] font-bold tracking-widest uppercase transition-colors bg-[#29b6f6]/10 hover:bg-[#29b6f6]/20 px-3 py-1.5 rounded-md border border-[#29b6f6]/20"
                        >{expandedCaseId === c.case_id ? 'Hide' : 'Expand'}</button>
                      </div>
                    </div>
                  </div>
                  {expandedCaseId === c.case_id && (
                    <div className="mt-4 pt-4 border-t border-[#242c3a] space-y-4">
                      <p className="text-[#c9d1dc] text-sm leading-relaxed font-[var(--font-sans)] bg-[#0f1117] p-3 rounded-xl border border-[#242c3a]">{c.justification}</p>
                      
                      <div className="bg-[#1e2433] rounded-xl p-3 border border-[#242c3a]">
                        <p className="font-bold text-[10px] text-[#29b6f6] mb-2 flex items-center gap-1.5 font-[var(--font-mono)] tracking-widest uppercase"><Info size={14}/>Cross-Reference Spans</p>
                        <div className="space-y-2">
                            <p className="text-[12px] text-[#f0f4f8] font-[var(--font-sans)] leading-relaxed"><strong className="text-[#6b7a8d] font-[var(--font-mono)] text-[10px] tracking-widest uppercase block mb-0.5">Local Target:</strong> {c.spans.target_span}</p>
                            <p className="text-[12px] text-[#f0f4f8] font-[var(--font-sans)] leading-relaxed"><strong className="text-[#6b7a8d] font-[var(--font-mono)] text-[10px] tracking-widest uppercase block mb-0.5">Global Candidate:</strong> {c.spans.candidate_span}</p>
                        </div>
                      </div>
                      
                      {typeof c.trs !== 'number' && showFactors && (
                        <div className="bg-[#0f1117] border border-[#242c3a] rounded-xl p-4">
                          <p className="text-[10px] font-bold text-[#6b7a8d] mb-3 font-[var(--font-mono)] tracking-widest uppercase border-b border-[#242c3a] pb-2">Algorithmic Breakdown</p>
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2">
                            {Object.entries(c.trs.factors).map(([k,v]) => (
                              <div key={k} className="flex justify-between items-center text-[11px] font-[var(--font-mono)]">
                                <span className="text-[#c9d1dc]">{k.replace(/_/g, ' ')}</span>
                                <span className="font-bold text-[#29b6f6]">{(v*100).toFixed(1)}%</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {/* Summary */}
      {data && (
        <div className="mt-4 bg-gradient-to-br from-[#161b25] to-[#0f1117] border border-[#29b6f6]/30 rounded-xl p-4 shadow-[0_0_20px_rgba(41,182,246,0.05)]">
          <p className="font-bold text-[#29b6f6] mb-2 font-[var(--font-mono)] tracking-widest uppercase text-[10px] flex items-center gap-2">
              <Sparkles size={12} /> GLOBAL SYSTEM SYNTHESIS
          </p>
          <p className="leading-relaxed text-[#f0f4f8] text-sm font-[var(--font-sans)]">{data.short_summary}</p>
        </div>
      )}
    </div>
  );
}