"use client";

import { useEffect, useState } from 'react';
import { ExternalLink, FileText, Search, Sparkles, X } from 'lucide-react';
import { apiFetch } from '@/lib/api';
import { googlePdfSearchUrl } from '@/lib/citationSources';

interface SelectedItem {
  id: string;
  type: 'chunk' | 'node';
  title: string;
  year?: number | null;
  citations?: number;
  trsScore?: number | null;
  similarityScore?: number | null;
}

interface CitationEvidence {
  title: string;
  source_title: string;
  source: 'cited_judgment' | 'uploaded_document' | 'unavailable';
  excerpt: string;
  citation_excerpt: string;
  article_refs: string[];
  pdf_url: string | null;
}

function EvidenceCard({ documentId, item }: { documentId: string; item: SelectedItem }) {
  const [evidence, setEvidence] = useState<CitationEvidence | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    apiFetch<{ context: CitationEvidence }>(
      `/api/ocr/citation-context/${encodeURIComponent(documentId)}/${encodeURIComponent(item.id)}`,
    ).then(response => {
      if (active) setEvidence(response.context);
    }).catch(reason => {
      if (active) setError(reason instanceof Error ? reason.message : 'Citation context unavailable');
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [documentId, item.id]);

  return (
    <article className="glass-card rounded-2xl p-5 space-y-4">
      <div>
        <h3 className="text-base font-bold leading-snug text-[#f0f4f8]">{item.title}</h3>
        <p className="mt-1 text-xs text-[#6b7a8d]">
          Cited case{item.year ? ` · ${item.year}` : ''}{item.citations ? ` · ${item.citations} reference${item.citations === 1 ? '' : 's'}` : ''}
        </p>
      </div>

      {loading ? (
        <p className="text-sm text-[#9aabbf]">Loading the cited judgment…</p>
      ) : error ? (
        <p className="text-sm text-[#fda4af]">{error}</p>
      ) : evidence ? (
        <>
          <div>
            <p className="text-[11px] font-bold uppercase tracking-wider text-[#29b6f6]">
              {evidence.source === 'cited_judgment' ? 'Passage from cited judgment' :
                evidence.source === 'uploaded_document' ? 'Mention in uploaded document' : 'Source passage unavailable'}
            </p>
            {evidence.excerpt ? (
              <blockquote className="mt-2 border-l-2 border-[#29b6f6] pl-3 text-sm leading-relaxed text-[#c9d1dc] whitespace-pre-wrap">
                {evidence.excerpt}
              </blockquote>
            ) : (
              <p className="mt-2 text-sm text-[#9aabbf]">No exact source passage could be retrieved for this citation.</p>
            )}
            {evidence.source === 'cited_judgment' && (
              <p className="mt-2 text-xs text-[#6b7a8d]">Source: {evidence.source_title}</p>
            )}
          </div>

          {evidence.article_refs.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {evidence.article_refs.map(article => (
                <span key={article} className="rounded-md bg-[#29b6f6]/10 px-2 py-1 text-xs text-[#81d4fa]">{article}</span>
              ))}
            </div>
          )}

          {evidence.source === 'cited_judgment' && evidence.citation_excerpt && (
            <details className="text-xs text-[#9aabbf]">
              <summary className="cursor-pointer">How your uploaded PDF cites this case</summary>
              <p className="mt-2 border-l border-[#a78bfa] pl-3 leading-relaxed">{evidence.citation_excerpt}</p>
            </details>
          )}
        </>
      ) : null}

      {(item.trsScore != null || item.similarityScore != null) && (
        <p className="text-xs text-[#9aabbf]">
          {item.trsScore != null && `TRS ${Math.round(item.trsScore * 100)}%`}
          {item.trsScore != null && item.similarityScore != null && ' · '}
          {item.similarityScore != null && `Similarity ${Math.round(item.similarityScore * 100)}%`}
        </p>
      )}

      <div className="flex flex-wrap gap-2 pt-2 border-t border-[#242c3a] text-xs">
        {evidence?.pdf_url && (
          <a href={evidence.pdf_url} target="_blank" rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 rounded-lg bg-[#29b6f6] px-3 py-2 font-semibold text-[#050a0e]">
            <FileText size={14} /> Open case PDF <ExternalLink size={12} />
          </a>
        )}
        <a href={googlePdfSearchUrl(item.title)} target="_blank" rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 rounded-lg border border-[#3b4a5e] px-3 py-2 text-[#c9d1dc] hover:text-white">
          <Search size={14} /> Google PDF search <ExternalLink size={12} />
        </a>
      </div>
    </article>
  );
}

export default function AnalysisWorkspace({ documentId, selectedItems, onItemDeselect }: {
  documentId: string;
  selectedItems: SelectedItem[];
  onItemDeselect: (id: string) => void;
}) {
  return (
    <div className="h-full glass-card rounded-2xl p-6 overflow-hidden flex flex-col">
      <div className="mb-6">
        <h2 className="text-lg font-bold text-[#f0f4f8] flex items-center gap-2 font-[var(--font-heading)]">
          <Sparkles size={20} className="text-[#29b6f6]" /> Workspace Analysis
        </h2>
        <p className="text-[#6b7a8d] text-xs mt-1.5 font-[var(--font-mono)] tracking-wider uppercase">
          {selectedItems.length ? `${selectedItems.length} selected source${selectedItems.length === 1 ? '' : 's'}` : 'Select a citation node'}
        </p>
      </div>

      {selectedItems.length === 0 ? (
        <div className="flex-1 flex items-center justify-center border-2 border-dashed border-[#242c3a] rounded-xl bg-[#161b25]/50">
          <p className="text-sm text-[#6b7a8d] text-center px-4">Select a cited case in Source Network to read its source passage here.</p>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto space-y-5 pr-2 scrollbar-thin">
          <div className="space-y-2">
            <h3 className="text-[#6b7a8d] text-xs font-bold font-[var(--font-mono)] tracking-widest uppercase">
              Selected Sources ({selectedItems.length})
            </h3>
            {selectedItems.map(item => (
              <div key={item.id} className="bg-[#1e2433] border border-[#242c3a] rounded-xl p-3 flex items-center justify-between gap-2">
                <span className="text-[#e8edf2] text-sm font-medium truncate">{item.title}</span>
                <button onClick={() => onItemDeselect(item.id)} aria-label={`Remove ${item.title}`}
                  className="text-[#6b7a8d] hover:text-[#f43f5e] bg-[#161b25] p-1.5 rounded-lg">
                  <X size={14} />
                </button>
              </div>
            ))}
          </div>
          {selectedItems.map(item => <EvidenceCard key={item.id} documentId={documentId} item={item} />)}
        </div>
      )}
    </div>
  );
}
