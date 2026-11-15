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
import { Upload, Network, MessageSquare, Fingerprint, Zap, BarChart2 } from 'lucide-react';
import ExternalInferencePanel from '@/components/ExternalInferencePanel';
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
  trsScore?: number | null;
  similarityScore?: number | null;
}

interface SelectedItem {
  id: string;
  type: 'node';
  title: string;
  year?: number | null;
  citations?: number;
  trsScore?: number | null;
  similarityScore?: number | null;
}

// Main application home page managing document selection and multi-view workspaces
function HomePage() {
  const { showToast } = useToast();
  const { user } = useAuth();
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null);
  const [nodes, setNodes] = useState<CitationNode[]>([]);
  const [edges, setEdges] = useState<{ source: string; target: string }[]>([]);
  const [selectedItems, setSelectedItems] = useState<SelectedItem[]>([]);
  const [selectedNodeIds, setSelectedNodeIds] = useState<string[]>([]);
  const [loadingCitations, setLoadingCitations] = useState(false);
  const [viewMode, setViewMode] = useState<'citation' | 'chat' | 'internal' | 'external'>('citation');
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
  const lastFetchKeyRef = useRef<string | null>(null);

  // Fetch citation graph data for active document
  const handleDocumentSelect = async (
    documentId: string,
    opts?: Partial<typeof graphQuery>,
    preserveSelection = false
  ) => {
    setSelectedDocumentId(documentId);
    const nextQuery = { ...graphQuery, ...opts };
    setGraphQuery(nextQuery);

    if (!preserveSelection) {
      setSelectedItems([]);
      setSelectedNodeIds([]);
    }

    if (!user) return;

    try {
      setLoadingCitations(true);

      const params = new URLSearchParams();
      params.set('limit', String(nextQuery.limit));
      if (nextQuery.layout) params.set('layout', nextQuery.layout);
      if (nextQuery.minCitations > 0) params.set('min_citations', String(nextQuery.minCitations));
      if (nextQuery.year) params.set('year', nextQuery.year);

      const response = await apiFetch<{
        nodes: Array<CitationNode & { trsScore?: number | null; similarityScore?: number | null }>;
        edges: { source: string; target: string }[];
        total_nodes: number;
        filtered_nodes: number;
        showing_top: number;
        has_more: boolean;
      }>(`/api/ocr/citation-nodes/${documentId}?${params.toString()}`);

      setNodes(
        response.nodes.map((n) => ({
          id: n.id,
          title: n.title,
          x: n.x,
          y: n.y,
          citations: n.citations,
          year: n.year,
          trsScore: n.trsScore ?? null,
          similarityScore: n.similarityScore ?? null,
        }))
      );
      setEdges(response.edges || []);

      setGraphStats({
        totalNodes: response.total_nodes || 0,
        filteredNodes: response.filtered_nodes || 0,
        showingTop: response.showing_top || 0,
        hasMore: response.has_more || false,
      });

      showToast({ message: 'Citation graph loaded', variant: 'success' });
    } catch (err) {
      console.error('Error fetching citation graph:', err);
      setNodes([]);
      setEdges([]);
      setGraphStats(null);
      showToast({ message: 'Failed to load citation graph', variant: 'error' });
    } finally {
      setLoadingCitations(false);
    }
  };

  // Re-fetch graph when filter parameters update
  useEffect(() => {
    if (!selectedDocumentId) return;
    const key = `${selectedDocumentId}|${graphQuery.limit}|${graphQuery.layout}|${debouncedMinCitations}|${debouncedYear}`;
    if (lastFetchKeyRef.current === key) return;
    lastFetchKeyRef.current = key;
    handleDocumentSelect(selectedDocumentId, { minCitations: debouncedMinCitations, year: debouncedYear }, true);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedDocumentId, debouncedMinCitations, debouncedYear]);

  const handleNodeSelect = (node: CitationNode) => {
    const isSelected = selectedNodeIds.includes(node.id);
    if (isSelected) {
      setSelectedNodeIds(selectedNodeIds.filter(id => id !== node.id));
      setSelectedItems(selectedItems.filter(item => item.id !== node.id));
    } else {
      setSelectedNodeIds([...selectedNodeIds, node.id]);
      setSelectedItems([...selectedItems, {
        id: node.id,
        type: 'node',
        title: node.title,
        year: node.year,
        citations: node.citations,
        trsScore: node.trsScore ?? null,
        similarityScore: node.similarityScore ?? null,
      }]);
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

  const handleUploadComplete = (documentId: string, mode: 'analysis' | 'database') => {
    showToast({ message: mode === 'database' ? 'Document added to local database' : 'Document processed — mapping sources', variant: 'success' });
    setViewMode(mode === 'database' ? 'chat' : 'citation');
    if (mode === 'database') {
      setSelectedDocumentId(documentId);
      setNodes([]);
      setEdges([]);
      setSelectedItems([]);
      setSelectedNodeIds([]);
    } else {
      handleDocumentSelect(documentId);
    }
  };

  const handleBackToUpload = () => {
    setSelectedDocumentId(null);
    setNodes([]);
    setEdges([]);
    setSelectedItems([]);
    setSelectedNodeIds([]);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  // Document analysis workspace view
  if (selectedDocumentId) {
    return (
      <div className="min-h-screen bg-[#0f1117]">
        <Navbar />
        <PrivacyBanner />
        <AuthModal />
        <div className="w-full px-3 sm:px-4 md:px-6 py-4 md:py-6">
          <div className="max-w-screen-2xl mx-auto">
            <div className="mb-6 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 animate-fade-up">
              <div className="glass-card rounded-xl p-1.5 flex gap-1.5 bg-[#161b25]/80 shadow-soft">
                {[
                  { key: 'citation', label: 'Source Network', icon: <Network size={16} /> },
                  { key: 'chat',     label: 'Chat',           icon: <MessageSquare size={16} /> },
                  { key: 'internal', label: 'Logic Analysis', icon: <Fingerprint size={16} /> },
                  { key: 'external', label: 'Global Scores', icon: <BarChart2 size={16} /> },
                ].map(({ key, label, icon }) => (
                  <button
                    key={key}
                    onClick={() => {
                      setViewMode(key as typeof viewMode);
                      // Global Scores can save new scores onto this document's
                      // citation graph nodes while Source Network isn't active.
                      // Reload the graph on return so those scores show up,
                      // preserving the currently selected nodes.
                      if (key === 'citation' && selectedDocumentId) {
                        handleDocumentSelect(selectedDocumentId, undefined, true);
                      }
                    }}
                    className={`px-4 py-2.5 rounded-lg transition-all inline-flex items-center gap-2 text-sm font-bold font-[var(--font-heading)] ${
                      viewMode === key
                        ? 'bg-[#29b6f6] text-[#050a0e] shadow-[0_0_15px_rgba(41,182,246,0.3)]'
                        : 'text-[#6b7a8d] hover:text-[#f0f4f8] hover:bg-[#1e2433]'
                    }`}
                  >
                    {icon} {label}
                  </button>
                ))}
              </div>
              <button
                onClick={handleBackToUpload}
                className="bg-[#29b6f6] hover:bg-[#03a9f4] text-[#050a0e] font-bold px-6 py-3 rounded-xl transition-all inline-flex items-center gap-2 text-sm shadow-[0_0_15px_rgba(41,182,246,0.25)]"
              >
                <Upload size={16} /> New Document
              </button>
            </div>

            <div className="flex flex-col lg:grid lg:grid-cols-4 gap-4 sm:gap-6 animate-fade-up">
              {/* Document Explorer sidebar */}
              <div className="w-full lg:col-span-1 h-[400px] sm:h-[500px] lg:h-[calc(100vh-220px)] border border-[#242c3a] rounded-2xl overflow-hidden glass-card shadow-soft">
                <DocumentExplorer
                  onDocumentSelect={handleDocumentSelect}
                  selectedDocumentId={selectedDocumentId}
                />
              </div>

              {/* Central interactive visualization and analysis panel */}
              <div className="w-full lg:col-span-2 h-[400px] sm:h-[500px] lg:h-[calc(100vh-220px)] border border-[#242c3a] rounded-2xl overflow-hidden bg-[#0f1117] shadow-soft relative">
                {viewMode === 'citation' && (
                  loadingCitations ? (
                    <div className="h-full flex items-center justify-center bg-[#0f1117]">
                      <p className="text-[#29b6f6] font-mono animate-pulse uppercase">Mapping Sources...</p>
                    </div>
                  ) : (
                    <CitationGraph
                      nodes={nodes}
                      edges={edges}
                      onNodeSelect={handleNodeSelect}
                      selectedNodeIds={selectedNodeIds}
                      onNodePositionUpdate={handleNodePositionUpdate}
                    />
                  )
                )}
                {viewMode === 'chat' && (
                  <ChatInterface key={selectedDocumentId} documentId={selectedDocumentId} />
                )}
                {viewMode === 'internal' && (
                  <InternalAnalysisPanel documentId={selectedDocumentId} />
                )}
                {viewMode === 'external' && (
                  <ExternalInferencePanel documentId={selectedDocumentId} />
                )}
              </div>

              {/* Inspector details panel */}
              <div className="w-full lg:col-span-1 h-[500px] sm:h-[600px] lg:h-[calc(100vh-220px)] border border-[#242c3a] rounded-2xl overflow-hidden glass-card shadow-soft">
                <AnalysisWorkspace
                  selectedItems={selectedItems}
                  onItemDeselect={handleItemDeselect}
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Landing page hero and upload interface
  return (
    <div className="min-h-screen bg-[#0f1117] relative overflow-x-hidden">
      <Navbar />
      <PrivacyBanner />
      <AuthModal />
      <div className="hero-blob w-[520px] h-[520px] bg-[#29b6f6] opacity-[0.055] top-[-160px] left-[-120px]" />
      <div className="hero-blob w-[400px] h-[400px] bg-[#1a6fa3] opacity-[0.07] top-[80px] right-[-100px]" />
      <div className="relative z-10 w-full px-4 sm:px-6 md:px-10 py-10 md:py-16">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-16 animate-fade-up">
            <div className="flex justify-center mb-6">
              <span className="badge-cyan pulse-cyan"><Zap size={14} className="mr-1" />CITE-AI</span>
            </div>
            <h1 className="text-4xl sm:text-4xl md:text-5xl font-bold text-[#f0f4f8] mb-6 font-[var(--font-heading)] leading-[1.06] tracking-[-0.04em]">
              YOUR PERSONAL AI<br />
              <span className="text-gradient-cyan">TO ANALYZE</span><br />
              &amp; VALIDATE DOCUMENTS
            </h1>
            <p className="text-[#6b7a8d] text-base sm:text-lg max-w-2xl mx-auto mb-8 leading-relaxed font-[var(--font-sans)]">
              We built the most powerful document analysis toolkit—OCR, source mapping,
              citation graphs, and logic validation—into one seamless workspace.
            </p>
          </div>
          <div className="mb-20 animate-fade-up relative z-20">
            <UploadPanel onUploadComplete={handleUploadComplete} />
          </div>
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
