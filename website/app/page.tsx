"use client"

import React, { useState, useEffect, useRef } from 'react';
import { AuthProvider } from '@/components/contexts/AuthContext';
import Navbar from '@/components/Navbar';
import PrivacyBanner from '@/components/PrivacyBanner';
import UploadPanel from '@/components/UploadPanel';
import DocumentExplorer from '@/components/DocumentExplorer';
import CitationGraph from '@/components/CitationGraph';
import AnalysisWorkspace from '@/components/AnalysisWorkspace';
import AuthModal from '@/components/AuthModal';
import { Upload, ArrowRight, Network, MessageSquare, BookOpen, Fingerprint, Zap, Shield, BarChart3 } from 'lucide-react';
import { useAuth } from '@/components/contexts/AuthContext';
import { apiFetch } from '@/lib/api';
import { useDebounce } from '@/hooks/useDebounce';
import ChatInterface from '@/components/ChatInterface';
import InternalAnalysisPanel from '@/components/InternalAnalysisPanel';
import { ToastProvider, useToast } from '@/components/ToastProvider';

interface CitationNode {
  id: string;
  title: string;
  x: number;
  y: number;
  citations: number;
  year: number;
}

interface SelectedItem {
  id: string;
  type: 'node';
  title: string;
}

function HomePage() {
  const { showToast } = useToast();
  const { user } = useAuth();
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null);
  const [nodes, setNodes] = useState<CitationNode[]>([]);
  const [selectedItems, setSelectedItems] = useState<SelectedItem[]>([]);
  const [selectedNodeIds, setSelectedNodeIds] = useState<string[]>([]);
  const [loadingCitations, setLoadingCitations] = useState(false);
  const [refreshDocuments, setRefreshDocuments] = useState(0);
  const [viewMode, setViewMode] = useState<'citation' | 'chat' | 'internal'>('citation');
  const [refreshingGraph, setRefreshingGraph] = useState(false);
  const [refreshingInternal, setRefreshingInternal] = useState(false);
  const [graphStats, setGraphStats] = useState<{
    totalNodes: number;
    filteredNodes: number;
    showingTop: number;
    hasMore: boolean;
  } | null>(null);

  const [graphQuery, setGraphQuery] = useState({
    limit: 50,
    layout: 'force' as 'force' | 'tree',
    minCitations: 0,
    year: ''
  });

  const isHeavyGraph = (graphStats?.showingTop ?? 0) >= 120 || graphQuery.limit >= 150;
  const dynamicDebounceMs = isHeavyGraph ? 800 : 300;
  const debouncedMinCitations = useDebounce(graphQuery.minCitations, dynamicDebounceMs);
  const debouncedYear = useDebounce(graphQuery.year, dynamicDebounceMs);
  const isDebouncePending = (
    graphQuery.minCitations !== debouncedMinCitations || graphQuery.year !== debouncedYear
  );
  const lastFetchKeyRef = useRef<string | null>(null);

  const handleDocumentSelect = async (documentId: string, opts?: Partial<typeof graphQuery>, preserveSelection = false) => {
    setSelectedDocumentId(documentId);
    const nextQuery = { ...graphQuery, ...opts };
    setGraphQuery(nextQuery);
    
    if (!preserveSelection) {
      setSelectedItems([]);
      setSelectedNodeIds([]);
    }

    const fetchKey = `${documentId}|${nextQuery.limit}|${nextQuery.layout}|${nextQuery.minCitations}|${nextQuery.year}`;
    lastFetchKeyRef.current = fetchKey;

    if (!user) return;

    try {
      setLoadingCitations(true);
      const params = new URLSearchParams();
      params.set('limit', String(nextQuery.limit));
      if (nextQuery.layout) params.set('layout', nextQuery.layout);
      if (nextQuery.minCitations > 0) params.set('min_citations', String(nextQuery.minCitations));
      if (nextQuery.year) params.set('year', nextQuery.year);

      const response = await apiFetch<{
        nodes: CitationNode[];
        edges: any[];
        total_nodes: number;
        filtered_nodes: number;
        showing_top: number;
        has_more: boolean;
      }>(`/api/ocr/citation-nodes/${documentId}?${params.toString()}`);

      setNodes(
        response.nodes.map((citation) => ({
          id: citation.id,
          title: citation.title,
          x: citation.x,
          y: citation.y,
          citations: citation.citations,
          year: citation.year,
        }))
      );

      setGraphStats({
        totalNodes: response.total_nodes || 0,
        filteredNodes: response.filtered_nodes || 0,
        showingTop: response.showing_top || 0,
        hasMore: response.has_more || false,
      });
    } catch (err) {
      console.error('Error fetching citation graph:', err);
      setNodes([]);
      setGraphStats(null);
    } finally {
      setLoadingCitations(false);
    }
  };

  useEffect(() => {
    if (!selectedDocumentId) return;
    const key = `${selectedDocumentId}|${graphQuery.limit}|${graphQuery.layout}|${debouncedMinCitations}|${debouncedYear}`;
    if (lastFetchKeyRef.current === key) return;
    handleDocumentSelect(selectedDocumentId, { minCitations: debouncedMinCitations, year: debouncedYear }, true);
    lastFetchKeyRef.current = key;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedDocumentId, debouncedMinCitations, debouncedYear]);

  const handleNodeSelect = (node: CitationNode) => {
    const isSelected = selectedNodeIds.includes(node.id);
    if (isSelected) {
      setSelectedNodeIds(selectedNodeIds.filter(id => id !== node.id));
      setSelectedItems(selectedItems.filter(item => item.id !== node.id));
    } else {
      setSelectedNodeIds([...selectedNodeIds, node.id]);
      setSelectedItems([...selectedItems, { id: node.id, type: 'node', title: node.title }]);
    }
  };

  const handleNodePositionUpdate = async (nodeId: string, x: number, y: number) => {
    if (!user || !selectedDocumentId) return;
    const uuidV4Regex = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
    if (!uuidV4Regex.test(nodeId)) return;
    
    try {
      await apiFetch(`/api/documents/${selectedDocumentId}/citations/${nodeId}`, {
        method: 'PUT',
        body: JSON.stringify({ x, y }),
      });
    } catch (err) {
      console.error('Error updating node position:', err);
    }
  };

  const handleItemDeselect = (id: string) => {
    setSelectedItems(selectedItems.filter(item => item.id !== id));
    setSelectedNodeIds(selectedNodeIds.filter(nodeId => nodeId !== id));
  };

  const handleUploadComplete = (documentId: string) => {
    showToast({ message: 'Processing started — Generating Insights', variant: 'info' });
    setRefreshDocuments(prev => prev + 1);
    setSelectedDocumentId(documentId);
    
    setLoadingCitations(true);
    apiFetch(`/api/ocr/process/${documentId}`, { method: 'POST' })
      .then(() => showToast({ message: 'Processing complete!', variant: 'success' }))
      .catch(err => {
        console.error('Error processing document after upload:', err);
        showToast({ message: 'Processing failed', variant: 'error' });
      })
      .finally(() => handleDocumentSelect(documentId));
  };

  const handleBackToUpload = () => {
    setSelectedDocumentId(null);
    setNodes([]);
    setSelectedItems([]);
    setSelectedNodeIds([]);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  /* ─── DASHBOARD VIEW ──────────────────────────────────────────── */
  if (selectedDocumentId) {
    return (
      <div className="min-h-screen bg-[#0f1117]">
        <Navbar />
        <PrivacyBanner />
        <AuthModal />

        <div className="w-full px-3 sm:px-4 md:px-6 py-4 md:py-6">
          <div className="max-w-screen-2xl mx-auto">

            {/* Top bar */}
            <div className="mb-6 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 animate-fade-up">
              {/* View Toggle */}
              <div className="glass-card rounded-xl p-1.5 flex gap-1.5 bg-[#161b25]/80 shadow-soft">
                {[
                  { key: 'citation', label: 'Source Network', icon: <Network size={16} /> },
                  { key: 'chat',     label: 'Chat',           icon: <MessageSquare size={16} /> },
                  { key: 'internal', label: 'Logic Analysis', icon: <Fingerprint size={16} /> },
                ].map(({ key, label, icon }) => (
                  <button
                    key={key}
                    onClick={() => setViewMode(key as typeof viewMode)}
                    className={`px-4 py-2.5 rounded-lg transition-all inline-flex items-center gap-2 text-sm font-bold font-[var(--font-heading)] ${
                      viewMode === key
                        ? 'bg-[#29b6f6] text-[#050a0e] shadow-[0_0_15px_rgba(41,182,246,0.3)]'
                        : 'text-[#6b7a8d] hover:text-[#f0f4f8] hover:bg-[#1e2433]'
                    }`}
                  >
                    {icon}
                    {label}
                    {viewMode === key && (key === 'citation' || key === 'internal') && (
                      <span
                        onClick={(e) => {
                          e.stopPropagation();
                          if (key === 'citation' && selectedDocumentId) {
                            setRefreshingGraph(true);
                            handleDocumentSelect(selectedDocumentId, {}, true)
                              .finally(() => {
                                setRefreshingGraph(false);
                                showToast({ message: 'Source graph refreshed', variant: 'success' });
                              });
                          } else if (key === 'internal' && selectedDocumentId) {
                            setRefreshingInternal(true);
                            showToast({ message: 'Recomputing logic analysis…', variant: 'info' });
                            apiFetch(`/api/ocr/internal-analysis/${selectedDocumentId}?force=1`)
                              .then(() => showToast({ message: 'Logic analysis refreshed', variant: 'success' }))
                              .catch(() => showToast({ message: 'Failed to refresh analysis', variant: 'error' }))
                              .finally(() => setRefreshingInternal(false));
                          }
                        }}
                        className={`ml-2 text-[10px] px-2 py-1 rounded cursor-pointer inline-flex items-center gap-1 font-[var(--font-mono)] tracking-widest border transition-colors ${
                          viewMode === key 
                            ? 'bg-[#050a0e]/20 hover:bg-[#050a0e]/40 border-[#050a0e]/20 text-[#050a0e]' 
                            : 'bg-[#050a0e]/40 hover:bg-[#050a0e]/80 border-[#f0f4f8]/10 text-[#f0f4f8]'
                        }`}
                      >
                        {(refreshingGraph || refreshingInternal) && (
                          <span className="inline-block h-3 w-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
                        )}
                        SYNC
                      </span>
                    )}
                  </button>
                ))}
              </div>

              {/* Upload CTA */}
              <button onClick={handleBackToUpload} className="bg-[#29b6f6] hover:bg-[#03a9f4] text-[#050a0e] font-bold px-6 py-3 rounded-xl transition-all inline-flex items-center gap-2 text-sm shadow-[0_0_15px_rgba(41,182,246,0.25)]">
                <Upload size={16} />
                New Document
              </button>
            </div>

            {/* Panels grid */}
            <div className="flex flex-col lg:grid lg:grid-cols-4 gap-4 sm:gap-6 animate-fade-up animate-fade-up-delay-1">
              {/* Document Explorer */}
              <div className="w-full lg:col-span-1 h-[400px] sm:h-[500px] lg:h-[calc(100vh-220px)] border border-[#242c3a] rounded-2xl overflow-hidden glass-card shadow-soft">
                <DocumentExplorer
                  onDocumentSelect={handleDocumentSelect}
                  selectedDocumentId={selectedDocumentId}
                  key={refreshDocuments}
                />
              </div>

              {/* Conditional main panels */}
              {viewMode === 'citation' ? (
                <>
                  {/* Citation Graph */}
                  <div className="w-full lg:col-span-2 h-[400px] sm:h-[500px] lg:h-[calc(100vh-220px)] border border-[#242c3a] rounded-2xl overflow-hidden bg-[#0f1117] shadow-soft relative">
                    {loadingCitations ? (
                      <div className="h-full flex items-center justify-center relative z-10 bg-[#0f1117]">
                        <div className="text-center">
                          <div className="w-14 h-14 border-4 border-[#1e2433] border-t-[#29b6f6] rounded-full animate-spin mx-auto mb-5 shadow-[0_0_15px_rgba(41,182,246,0.2)]" />
                          <p className="text-[#29b6f6] text-sm font-bold font-[var(--font-mono)] tracking-widest uppercase">MAPPING SOURCES…</p>
                        </div>
                      </div>
                    ) : (
                      <div className="h-full flex flex-col relative z-10">
                        {graphStats && graphStats.totalNodes > 0 && (
                          <div className="bg-[#161b25]/90 backdrop-blur-md border-b border-[#242c3a] px-5 py-3 flex items-center justify-between text-xs gap-4 flex-wrap z-20">
                            <div className="flex gap-5 text-[#6b7a8d] font-[var(--font-mono)] tracking-wider">
                              <span>TOTAL <strong className="text-[#f0f4f8]">{graphStats.totalNodes}</strong></span>
                              <span>SHOWING <strong className="text-[#29b6f6]">{graphStats.showingTop}</strong></span>
                              {graphStats.hasMore && (
                                <span className="text-amber-400 bg-amber-400/10 px-2 py-0.5 rounded border border-amber-400/20">+{graphStats.totalNodes - graphStats.showingTop} MORE</span>
                              )}
                            </div>
                            <div className="flex items-center gap-3">
                              {graphStats.hasMore && (
                                <button
                                  onClick={() => {
                                    setGraphQuery(q => {
                                      const nextLimit = Math.min(q.limit + 50, 200);
                                      handleDocumentSelect(selectedDocumentId!, { limit: nextLimit });
                                      return { ...q, limit: nextLimit };
                                    });
                                  }}
                                  className="text-[#29b6f6] hover:text-[#f0f4f8] font-bold font-[var(--font-mono)] uppercase tracking-wider text-[10px] transition-colors"
                                >
                                  Load More
                                </button>
                              )}
                              <select
                                value={graphQuery.layout}
                                onChange={e => {
                                  const layout = e.target.value as 'force' | 'tree';
                                  setGraphQuery(q => ({ ...q, layout }));
                                  if (selectedDocumentId) handleDocumentSelect(selectedDocumentId, { layout }, true);
                                }}
                                className="text-xs px-3 py-1.5 border border-[#242c3a] rounded-lg bg-[#0b0e15] text-[#f0f4f8] outline-none focus:border-[#29b6f6] font-[var(--font-mono)]"
                              >
                                <option value="force">Force</option>
                                <option value="tree">Tree</option>
                              </select>
                              <input
                                type="number"
                                min={0}
                                placeholder="Min links"
                                value={graphQuery.minCitations || ''}
                                onChange={e => setGraphQuery(q => ({ ...q, minCitations: e.target.value ? parseInt(e.target.value, 10) : 0 }))}
                                className="w-24 text-xs px-3 py-1.5 border border-[#242c3a] rounded-lg bg-[#0b0e15] text-[#f0f4f8] placeholder-[#6b7a8d] outline-none focus:border-[#29b6f6] font-[var(--font-mono)]"
                              />
                              {isDebouncePending && !loadingCitations && (
                                <div className="flex items-center gap-2 text-[#6b7a8d]">
                                  <span className="inline-block h-4 w-4 border-2 border-[#242c3a] border-t-[#29b6f6] rounded-full animate-spin" />
                                </div>
                              )}
                              <button
                                onClick={() => handleDocumentSelect(selectedDocumentId!, { limit: 50 })}
                                className="text-[10px] font-bold tracking-widest uppercase px-3 py-1.5 border border-[#242c3a] rounded-lg bg-[#1e2433] text-[#f0f4f8] hover:bg-[#242c3a] transition-colors"
                              >
                                Reset
                              </button>
                            </div>
                          </div>
                        )}
                        <CitationGraph
                          nodes={nodes}
                          onNodeSelect={handleNodeSelect}
                          selectedNodeIds={selectedNodeIds}
                          onNodePositionUpdate={handleNodePositionUpdate}
                        />
                      </div>
                    )}
                  </div>

                  {/* Analysis Workspace */}
                  <div className="w-full lg:col-span-1 h-[500px] sm:h-[600px] lg:h-[calc(100vh-220px)] border border-[#242c3a] rounded-2xl overflow-hidden glass-card shadow-soft">
                    <AnalysisWorkspace selectedItems={selectedItems} onItemDeselect={handleItemDeselect} />
                  </div>
                </>
              ) : viewMode === 'chat' ? (
                <div className="w-full lg:col-span-3 h-[600px] sm:h-[700px] lg:h-[calc(100vh-220px)] border border-[#242c3a] rounded-2xl overflow-hidden shadow-soft">
                  <ChatInterface documentId={selectedDocumentId} />
                </div>
              ) : (
                <div className="w-full lg:col-span-3 h-[600px] sm:h-[700px] lg:h-[calc(100vh-220px)] border border-[#242c3a] rounded-2xl overflow-hidden shadow-soft">
                  <InternalAnalysisPanel documentId={selectedDocumentId} />
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  /* ─── LANDING / HERO VIEW ─────────────────────────────────────── */
  return (
    <div className="min-h-screen bg-[#0f1117] relative overflow-x-hidden">
      <Navbar />
      <PrivacyBanner />
      <AuthModal />

      {/* Ambient glow blobs */}
      <div className="hero-blob w-[520px] h-[520px] bg-[#29b6f6] opacity-[0.055] top-[-160px] left-[-120px]" />
      <div className="hero-blob w-[400px] h-[400px] bg-[#1a6fa3] opacity-[0.07] top-[80px] right-[-100px]" />
      <div className="hero-blob w-[300px] h-[300px] bg-[#29b6f6] opacity-[0.04] bottom-[120px] left-[30%]" />

      <div className="relative z-10 w-full px-4 sm:px-6 md:px-10 py-10 md:py-16">
        <div className="max-w-5xl mx-auto">

          {/* ── Hero ── */}
          <div className="text-center mb-16 animate-fade-up">
            {/* Eyebrow badge */}
            <div className="flex justify-center mb-6">
              <span className="badge-cyan pulse-cyan">
                <Zap size={14} className="mr-1" />
                CITE-AI
              </span>
            </div>
            <h1 className="text-4xl sm:text-4xl md:text-5xl font-bold text-[#f0f4f8] mb-6 font-[var(--font-heading)] leading-[1.06] tracking-[-0.04em]">
              YOUR PERSONAL AI<br />
              <span className="text-gradient-cyan">TO ANALYZE</span><br />
              &amp; VALIDATE DOCUMENTS
            </h1>
            <p className="text-[#6b7a8d] text-base sm:text-lg max-w-2xl mx-auto mb-8 leading-relaxed font-[var(--font-sans)]">
              We built the most powerful document analysis toolkit—OCR, source mapping, citation graphs, and logic validation—into one seamless workspace.
            </p>

            {/* Feature bullets */}
            <div className="flex flex-col sm:flex-row items-center justify-center gap-3 sm:gap-6 mb-10 text-sm">
              {['INGEST complex PDFs instantly', 'MAP citation networks visually', 'VALIDATE source logic chains', 'QUERY with context-aware AI'].map((item) => (
                <div key={item} className="flex items-center gap-2 text-[#c9d1dc] font-medium font-[var(--font-sans)]">
                  <span className="w-2 h-2 rounded-full bg-[#29b6f6] pulse-cyan flex-shrink-0" />
                  {item}
                </div>
              ))}
            </div>

            {/* CTA row */}
            <div className="flex items-center justify-center gap-4 flex-wrap">
              <span className="text-[11px] text-[#6b7a8d] font-bold font-[var(--font-mono)] tracking-widest uppercase bg-[#161b25] px-4 py-1.5 rounded-full border border-[#242c3a]">AI-Powered Analysis</span>
            </div>
          </div>

          {/* ── Upload Panel ── */}
          <div className="mb-20 animate-fade-up animate-fade-up-delay-1 relative z-20">
            <UploadPanel onUploadComplete={handleUploadComplete} />
          </div>
          {/* ── Why Section ── */}
          <div className="mb-20 animate-fade-up animate-fade-up-delay-2 relative z-10">
            <div className="text-center mb-12">
              <p className="badge-cyan inline-flex mx-auto mb-4">WHY RESEARCHERS LOVE US</p>
              <h2 className="text-3xl sm:text-4xl font-bold font-[var(--font-heading)] text-[#f0f4f8] tracking-tight">
                Everything you need to trust your sources
              </h2>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
              {[
                {
                  icon: <Upload size={22} className="text-[#f0f4f8]" />,
                  title: 'Ingest & Parse',
                  desc: 'Securely upload complex PDF files. Our OCR pipeline extracts every detail with high fidelity — tables, footnotes, figures.',
                  delay: '',
                },
                {
                  icon: <Network size={22} className="text-[#f0f4f8]" />,
                  title: 'Validate Sources',
                  desc: 'Visualize citation relationships as an interactive graph. Cross-reference internal logic chains and detect circular dependencies.',
                  delay: 'animate-fade-up-delay-1',
                },
                {
                  icon: <BookOpen size={22} className="text-[#f0f4f8]" />,
                  title: 'Extract Insights',
                  desc: 'Query your parsed corpus to generate rapid, accurate summaries. Chat with your document like it\'s a subject-matter expert.',
                  delay: 'animate-fade-up-delay-2',
                },
                {
                  icon: <BarChart3 size={22} className="text-[#f0f4f8]" />,
                  title: 'Logic Analysis',
                  desc: 'Deep structural analysis of argument chains. Spot contradictions, unsupported claims, and reasoning gaps automatically.',
                  delay: '',
                },
                {
                  icon: <Shield size={22} className="text-[#f0f4f8]" />,
                  title: 'Privacy First',
                  desc: 'Your documents stay yours. End-to-end encryption, isolated processing environments, zero data sharing.',
                  delay: 'animate-fade-up-delay-1',
                },
                {
                  icon: <Zap size={22} className="text-[#f0f4f8]" />,
                  title: 'Lightning Fast',
                  desc: 'Sub-second graph rendering. Instant semantic search. Real-time citation updates as you annotate.',
                  delay: 'animate-fade-up-delay-2',
                },
              ].map(({ icon, title, desc, delay }) => (
                <div
                  key={title}
                  className={`glass-card glass-card-hover rounded-3xl p-8 animate-fade-up ${delay}`}
                >
                  <div className="icon-wrap mb-5">{icon}</div>
                  <h3 className="text-lg font-bold text-[#f0f4f8] mb-3 font-[var(--font-heading)] tracking-tight">
                    {title}
                  </h3>
                  <p className="text-sm text-[#6b7a8d] leading-relaxed font-[var(--font-sans)]">{desc}</p>
                </div>
              ))}
            </div>
          </div>

          <hr className="divider mb-16" />

          {/* ── Recent Workspaces (auth only) ── */}
          {user && (
            <div className="animate-fade-up animate-fade-up-delay-2 mb-10">
              <div className="glass-card rounded-3xl p-8 border border-[#242c3a] shadow-soft">
                <div className="flex items-center justify-between mb-6">
                  <div>
                    <h3 className="text-2xl font-bold text-[#f0f4f8] font-[var(--font-heading)] tracking-tight">
                      Recent Workspaces
                    </h3>
                    <p className="text-[11px] text-[#29b6f6] mt-1.5 font-[var(--font-mono)] font-bold tracking-widest uppercase">PICK UP WHERE YOU LEFT OFF</p>
                  </div>
                  <div className="w-10 h-10 rounded-xl bg-[#1e2433] flex items-center justify-center border border-[#242c3a]">
                    <ArrowRight className="text-[#29b6f6]" size={20} />
                  </div>
                </div>
                <div className="bg-[#0b0e15] rounded-2xl overflow-hidden border border-[#242c3a]">
                  <DocumentExplorer
                    onDocumentSelect={handleDocumentSelect}
                    selectedDocumentId={selectedDocumentId}
                    key={refreshDocuments}
                  />
                </div>
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}

export default function Home() {
  return (
    <AuthProvider>
      <ToastProvider>
        <HomePage />
      </ToastProvider>
    </AuthProvider>
  );
}