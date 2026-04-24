"use client"

import React, { useState } from 'react';
import { ThumbsUp, ThumbsDown, ChevronDown, ChevronUp } from 'lucide-react';

interface Result {
  id: string;
  sourceTitle: string;
  metadata: {
    year: number;
    sourceType: string; 
    references: number; 
  };
  risk: 'low' | 'medium' | 'high';
  sentiment: 'positive' | 'neutral' | 'negative';
  trs: number;
  explanation: string;
  irac: {
    issue: string;
    rule: string;
    application: string;
    conclusion: string;
  };
}

interface ResultCardProps {
  result: Result;
  onFeedback?: (resultId: string, feedback: 'up' | 'down') => void;
}

export default function ResultCard({ result, onFeedback }: ResultCardProps) {
  const [showFullReasoning, setShowFullReasoning] = useState(false);
  const [feedback, setFeedback] = useState<'up' | 'down' | null>(null);

  const getRiskColor = (risk: string) => {
    switch (risk) {
      case 'low': return 'bg-[rgba(41,182,246,0.1)] text-[#29b6f6] border-[rgba(41,182,246,0.25)]';
      case 'medium': return 'bg-amber-500/10 text-amber-400 border-amber-500/25';
      case 'high': return 'bg-[#f43f5e]/10 text-[#f43f5e] border-[#f43f5e]/25';
      default: return 'bg-[#1a1f2e] text-[#c9d1dc] border-[#242c3a]';
    }
  };

  const getSentimentColor = (sentiment: string) => {
    switch (sentiment) {
      case 'positive': return 'bg-[rgba(41,182,246,0.1)] text-[#29b6f6] border-[rgba(41,182,246,0.25)]';
      case 'neutral': return 'bg-[#1a1f2e] text-[#c9d1dc] border-[#242c3a]';
      case 'negative': return 'bg-orange-500/10 text-orange-400 border-orange-500/25';
      default: return 'bg-[#1a1f2e] text-[#c9d1dc] border-[#242c3a]';
    }
  };

  const handleFeedback = (type: 'up' | 'down') => {
    setFeedback(type);
    onFeedback?.(result.id, type);
  };

  return (
    <div className="glass-card rounded-2xl p-5 glass-card-hover group">
      {/* Header */}
      <div className="mb-4">
        <h3 className="text-base sm:text-lg font-bold text-[#f0f4f8] mb-2 leading-snug font-[var(--font-heading)] group-hover:text-[#29b6f6] transition-colors">{result.sourceTitle}</h3>
        <div className="flex items-center gap-3 text-[11px] sm:text-xs text-[#6b7a8d] flex-wrap font-[var(--font-mono)]">
          <span>{result.metadata.year}</span>
          <span className="text-[#242c3a]">•</span>
          <span>{result.metadata.sourceType}</span>
          <span className="text-[#242c3a]">•</span>
          <span>{result.metadata.references} REFERENCES</span>
        </div>
      </div>

      {/* Badges */}
      <div className="flex items-center gap-2 mb-5 flex-wrap">
        <span className={`px-2.5 py-1 rounded-full text-[10px] font-bold font-[var(--font-mono)] tracking-wider border ${getRiskColor(result.risk)} uppercase`}>
          {result.risk} RISK
        </span>
        <span className={`px-2.5 py-1 rounded-full text-[10px] font-bold font-[var(--font-mono)] tracking-wider border ${getSentimentColor(result.sentiment)} uppercase`}>
          {result.sentiment}
        </span>
      </div>

      {/* TRS Score */}
      <div className="mb-5 bg-[#0b0e15] rounded-xl p-3 border border-[#242c3a]">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[#6b7a8d] font-bold text-[10px] font-[var(--font-mono)] tracking-widest uppercase">Relevance Score</span>
          <span className="text-[#f0f4f8] font-bold text-sm font-[var(--font-mono)]">{result.trs}%</span>
        </div>
        <div className="w-full h-1.5 bg-[#1e2433] rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-[#1a6fa3] to-[#29b6f6] rounded-full transition-all duration-500 relative"
            style={{ width: `${result.trs}%` }}
          >
            <div className="absolute inset-0 bg-white/20"></div>
          </div>
        </div>
      </div>

      {/* Explanation */}
      <div className="mb-5">
        <p className="text-[#c9d1dc] text-sm leading-relaxed font-[var(--font-sans)]">{result.explanation}</p>
      </div>

      {/* Full Reasoning */}
      <button
        onClick={() => setShowFullReasoning(!showFullReasoning)}
        className="w-full bg-[#0b0e15] hover:bg-[#1a1f2e] text-[#f0f4f8] font-bold py-2.5 px-4 rounded-xl transition-all flex items-center justify-between mb-4 text-xs border border-[#242c3a] font-[var(--font-heading)]"
      >
        <span className="tracking-wide">VIEW FULL REASONING</span>
        {showFullReasoning ? <ChevronUp size={16} className="text-[#29b6f6]" /> : <ChevronDown size={16} className="text-[#6b7a8d]" />}
      </button>

      {showFullReasoning && (
        <div className="bg-[#0b0e15] rounded-xl p-4 mb-4 space-y-4 border border-[#242c3a]">
          <div>
            <h4 className="text-[#29b6f6] font-bold text-[10px] tracking-widest mb-1.5 font-[var(--font-mono)]">CONTEXT</h4>
            <p className="text-[#c9d1dc] text-xs leading-relaxed font-[var(--font-sans)]">{result.irac.issue}</p>
          </div>
          <div className="h-px w-full bg-[#1e2433]"></div>
          <div>
            <h4 className="text-[#a78bfa] font-bold text-[10px] tracking-widest mb-1.5 font-[var(--font-mono)]">FRAMEWORK</h4>
            <p className="text-[#c9d1dc] text-xs leading-relaxed font-[var(--font-sans)]">{result.irac.rule}</p>
          </div>
          <div className="h-px w-full bg-[#1e2433]"></div>
          <div>
            <h4 className="text-[#fb923c] font-bold text-[10px] tracking-widest mb-1.5 font-[var(--font-mono)]">APPLICATION</h4>
            <p className="text-[#c9d1dc] text-xs leading-relaxed font-[var(--font-sans)]">{result.irac.application}</p>
          </div>
          <div className="h-px w-full bg-[#1e2433]"></div>
          <div>
            <h4 className="text-[#29b6f6] font-bold text-[10px] tracking-widest mb-1.5 font-[var(--font-mono)]">CONCLUSION</h4>
            <p className="text-[#f0f4f8] font-medium text-xs leading-relaxed font-[var(--font-sans)]">{result.irac.conclusion}</p>
          </div>
        </div>
      )}

      {/* Feedback Buttons */}
      <div className="flex items-center justify-between pt-4 border-t border-[#242c3a]">
        <span className="text-[#6b7a8d] text-xs font-[var(--font-sans)] font-medium">Was this helpful?</span>
        <div className="flex items-center gap-2">
          <button
            onClick={() => handleFeedback('up')}
            className={`p-2 rounded-lg transition-all ${
              feedback === 'up'
                ? 'bg-[rgba(41,182,246,0.1)] text-[#29b6f6] border border-[rgba(41,182,246,0.3)] shadow-[0_0_10px_rgba(41,182,246,0.2)]'
                : 'bg-[#1e2433] hover:bg-[#242c3a] text-[#6b7a8d] border border-[#242c3a]'
            }`}
          >
            <ThumbsUp size={14} />
          </button>
          <button
            onClick={() => handleFeedback('down')}
            className={`p-2 rounded-lg transition-all ${
              feedback === 'down'
                ? 'bg-[#f43f5e]/10 text-[#f43f5e] border border-[#f43f5e]/30 shadow-[0_0_10px_rgba(244,63,94,0.2)]'
                : 'bg-[#1e2433] hover:bg-[#242c3a] text-[#6b7a8d] border border-[#242c3a]'
            }`}
          >
            <ThumbsDown size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}