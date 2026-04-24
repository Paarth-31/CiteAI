"use client";

import React, { useEffect, useState } from 'react';
import { apiFetch } from '@/lib/api';
import { Fingerprint, AlertTriangle } from 'lucide-react';

interface InternalAnalysisPanelProps {
  documentId: string | null;
}

interface AnalysisResult {
  [key: string]: any;
}

export default function InternalAnalysisPanel({ documentId }: InternalAnalysisPanelProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);

  useEffect(() => {
    if (!documentId) return;
    setLoading(true);
    setError(null);
    apiFetch<{ success?: boolean; analysis?: AnalysisResult; error?: string }>(`/api/ocr/internal-analysis/${documentId}`)
      .then(res => {
        if (res.error) {
          setError(res.error);
        } else {
          setAnalysis(res.analysis || null);
        }
      })
      .catch(err => {
        setError(err.message || 'Failed to load analysis logs');
      })
      .finally(() => setLoading(false));
  }, [documentId]);

  if (!documentId) {
    return (
      <div className="glass-card rounded-2xl p-6 h-full flex flex-col items-center justify-center text-center">
        <Fingerprint size={40} className="text-[#242c3a] mb-4" />
        <p className="text-[#6b7a8d] text-sm font-[var(--font-sans)]">Select a document to view logic architecture.</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="glass-card rounded-2xl p-6 h-full flex flex-col items-center justify-center text-center">
        <div className="w-12 h-12 border-2 border-[#242c3a] border-t-[#29b6f6] rounded-full animate-spin mb-5" />
        <p className="text-[#e8edf2] text-sm font-bold font-[var(--font-heading)] tracking-wide">Deconstructing Logic Chains...</p>
        <p className="text-[11px] text-[#6b7a8d] mt-2 font-[var(--font-mono)] uppercase tracking-widest">Warming up neural pathways</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="glass-card rounded-2xl p-6 h-full flex flex-col">
        <h3 className="text-xl font-bold mb-4 text-[#f43f5e] font-[var(--font-heading)] flex items-center gap-2"><AlertTriangle size={20} /> Analysis Fault</h3>
        <p className="text-sm text-[#f0f4f8] mb-3 bg-[#f43f5e]/10 p-4 rounded-xl border border-[#f43f5e]/20">{error}</p>
        <p className="text-xs text-[#6b7a8d] font-[var(--font-mono)] uppercase tracking-wider">Execute re-upload or check pipeline status.</p>
      </div>
    );
  }

  if (!analysis) {
    return (
      <div className="glass-card rounded-2xl p-6 h-full flex items-center justify-center text-sm text-[#6b7a8d] font-[var(--font-sans)]">
        No structural data extracted yet.
      </div>
    );
  }

  const coherenceScore = analysis?.['Final Report']?.['Coherence Score'] ?? null;
  const claims: string[] = analysis?.Claims || [];
  const contradictions: string[] = analysis?.Contradictions || analysis?.['Detected Contradictions'] || [];
  const briefCommentary = analysis?.['Final Report']?.['Brief Commentary'] || analysis?.['Brief Commentary'] || '';
  const keyFlows = analysis?.['Final Report']?.['Key Argument Flows'] || analysis?.['Key Argument Flows'] || [];

  return (
    <div className="glass-card rounded-2xl p-6 h-full flex flex-col overflow-hidden">
      <div className="flex flex-wrap items-center justify-between mb-5 gap-4 border-b border-[#242c3a] pb-4">
        <h3 className="text-xl font-bold text-[#f0f4f8] font-[var(--font-heading)] flex items-center gap-3">
          <div className="bg-[#29b6f6]/10 p-1.5 rounded-lg border border-[#29b6f6]/20">
            <Fingerprint size={20} className="text-[#29b6f6]" />
          </div>
          Logic Architecture
        </h3>
        {coherenceScore !== null && (
          <div className="flex items-center gap-2 bg-[#161b25] border border-[#242c3a] rounded-lg p-1.5">
            <span className="text-[10px] text-[#6b7a8d] font-bold font-[var(--font-mono)] tracking-widest uppercase pl-1">Integrity</span>
            <span className="text-[11px] px-2 py-1 rounded bg-[#29b6f6]/20 text-[#29b6f6] border border-[#29b6f6]/30 font-bold font-[var(--font-mono)]">
              {(coherenceScore * 100).toFixed(1)}%
            </span>
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-thin space-y-6 pr-2">
        <section className="bg-[#161b25] border border-[#242c3a] rounded-xl p-4 shadow-sm">
          <h4 className="text-[10px] font-bold text-[#29b6f6] mb-3 font-[var(--font-mono)] tracking-widest uppercase">STRUCTURAL SUMMARY</h4>
          <p className="text-sm leading-relaxed text-[#c9d1dc] whitespace-pre-line font-[var(--font-sans)]">
            {briefCommentary || 'Processing output unavailable.'}
          </p>
        </section>

        <section className="px-2">
          <h4 className="text-[10px] font-bold text-[#a78bfa] mb-3 font-[var(--font-mono)] tracking-widest uppercase flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-[#a78bfa]"></span> PRIMARY DATA FLOWS
          </h4>
          {keyFlows && keyFlows.length > 0 ? (
            <ul className="space-y-2.5 pl-3 border-l-2 border-[#1e2433]">
              {keyFlows.slice(0, 8).map((f: string, i: number) => (
                <li key={i} className="text-xs text-[#c9d1dc] leading-relaxed font-[var(--font-sans)] relative">
                  <span className="absolute -left-[17px] top-1.5 w-1.5 h-1.5 rounded-full bg-[#242c3a]"></span>
                  {f}
                </li>
              ))}
              {keyFlows.length > 8 && (
                <li className="text-[10px] text-[#6b7a8d] font-bold font-[var(--font-mono)] tracking-wider mt-2">+ {keyFlows.length - 8} MORE PIPELINES HIDDEN</li>
              )}
            </ul>
          ) : (
            <p className="text-xs text-[#6b7a8d] italic">No logical pipelines established.</p>
          )}
        </section>

        <section className="px-2">
          <h4 className="text-[10px] font-bold text-[#29b6f6] mb-3 font-[var(--font-mono)] tracking-widest uppercase flex items-center gap-2">
             <span className="w-1.5 h-1.5 rounded-full bg-[#29b6f6]"></span> VALIDATED CLAIMS <span className="bg-[#1e2433] text-[#f0f4f8] px-1.5 rounded ml-1">{claims.length}</span>
          </h4>
          {claims.length > 0 ? (
            <ul className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {claims.slice(0, 10).map((c, i) => (
                <li key={i} className="text-xs text-[#f0f4f8] bg-[#161b25] border border-[#242c3a] p-3 rounded-xl leading-relaxed font-[var(--font-sans)] shadow-sm">
                  {c.slice(0, 160)}{c.length > 160 ? '…' : ''}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-[#6b7a8d] italic">Zero claims verified.</p>
          )}
          {claims.length > 10 && (
             <p className="text-[10px] text-[#6b7a8d] font-bold font-[var(--font-mono)] tracking-wider mt-3 pl-2">+ {claims.length - 10} ADDITIONAL CLAIMS OMITTED</p>
          )}
        </section>

        <section className="px-2 pb-4">
          <h4 className="text-[10px] font-bold text-[#f43f5e] mb-3 font-[var(--font-mono)] tracking-widest uppercase flex items-center gap-2">
             <span className="w-1.5 h-1.5 rounded-full bg-[#f43f5e] animate-pulse"></span> DETECTED LOGIC FAULTS <span className="bg-[#f43f5e]/20 text-[#f43f5e] px-1.5 rounded ml-1">{contradictions.length}</span>
          </h4>
          {contradictions.length > 0 ? (
            <ul className="space-y-3">
              {contradictions.slice(0, 6).map((c, i) => (
                <li key={i} className="text-xs text-[#f0f4f8] bg-[#f43f5e]/10 p-3 rounded-xl border border-[#f43f5e]/30 leading-relaxed shadow-[0_0_15px_rgba(244,63,94,0.05)] relative overflow-hidden group">
                  <div className="absolute left-0 top-0 bottom-0 w-1 bg-[#f43f5e]"></div>
                  <span className="pl-2 block font-[var(--font-sans)]">{c.slice(0, 200)}{c.length > 200 ? '…' : ''}</span>
                </li>
              ))}
              {contradictions.length > 6 && (
                <li className="text-[10px] text-[#6b7a8d] font-bold font-[var(--font-mono)] tracking-wider mt-2">+ {contradictions.length - 6} CRITICAL FAULTS OVERFLOW</li>
              )}
            </ul>
          ) : (
            <div className="bg-[#10b981]/10 border border-[#10b981]/20 rounded-xl p-4 flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-[#10b981]/20 flex items-center justify-center shrink-0">
                <span className="text-[#10b981] font-bold text-lg leading-none">✓</span>
              </div>
              <div>
                <p className="text-sm font-bold text-[#10b981] font-[var(--font-heading)]">Zero Contradictions Found</p>
                <p className="text-xs text-[#10b981]/70 font-[var(--font-sans)] mt-0.5">The structural integrity of this document is sound.</p>
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}