"use client"

import React, { useState, useEffect } from 'react';
import { FileText, Loader2, ArrowRight } from 'lucide-react';
import { useAuth } from '@/components/contexts/AuthContext';
import { apiFetch } from '@/lib/api';

interface Document {
  id: string;
  title: string;
  fileUrl: string;
  fileSize: number;
  uploadDate: string;
  status: string;
}

interface DocumentExplorerProps {
  onDocumentSelect: (documentId: string) => void;
  selectedDocumentId: string | null;
}

export default function DocumentExplorer({ onDocumentSelect, selectedDocumentId }: DocumentExplorerProps) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { user, isLoading: authLoading, showAuthModal } = useAuth();

  useEffect(() => {
    if (!authLoading) {
      if (user) {
        fetchDocuments();
      } else {
        setLoading(false);
        setDocuments([]);
      }
    }
  }, [user, authLoading]);

  const fetchDocuments = async () => {
    try {
      setLoading(true);
      try {
        const data = await apiFetch<Document[]>(`/api/documents`);
        setDocuments(data);
        setError(null);
      } catch (err) {
        setError('Please sign in to view your documents');
        setDocuments([]);
        console.error(err);
      }
    } finally {
      setLoading(false);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  if (authLoading) {
    return (
      <div className="h-full glass-card rounded-2xl p-6 flex flex-col items-center justify-center">
        <Loader2 className="animate-spin text-[#29b6f6]" size={32} />
        <p className="text-[#6b7a8d] font-[var(--font-mono)] text-xs mt-4 tracking-widest uppercase">Fetching Workspaces</p>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="h-full glass-card rounded-2xl p-8 flex flex-col items-center justify-center text-center">
        <div className="w-16 h-16 bg-[#161b25] border border-[#242c3a] rounded-2xl flex items-center justify-center mb-6 shadow-inner">
          <FileText size={28} className="text-[#6b7a8d]" />
        </div>
        <h3 className="text-xl font-bold text-[#f0f4f8] mb-3 font-[var(--font-heading)]">Authentication Required</h3>
        <p className="text-[#6b7a8d] text-sm mb-6 leading-relaxed">
          Sign in to access your secure document analysis workspaces.
        </p>
        <button
          onClick={() => showAuthModal('signIn')}
          className="btn-primary"
        >
          Sign In Now
        </button>
      </div>
    );
  }

  return (
    <div className="h-full glass-card rounded-2xl p-5 overflow-hidden flex flex-col">
      <div className="mb-5 pb-4 border-b border-[#242c3a]">
        <h2 className="text-lg font-bold text-[#f0f4f8] flex items-center gap-2.5 font-[var(--font-heading)] tracking-tight">
          <div className="bg-[#29b6f6]/10 p-1.5 rounded-lg border border-[#29b6f6]/20 text-[#29b6f6]">
            <FileText size={18} />
          </div>
          Active Workspaces
        </h2>
        <p className="text-[#6b7a8d] text-[11px] mt-2 font-[var(--font-mono)] tracking-widest uppercase">
          {loading ? 'SYNCING...' : `${documents.length} DOCUMENT${documents.length !== 1 ? 'S' : ''} FOUND`}
        </p>
      </div>

      {loading ? (
        <div className="flex-1 flex flex-col items-center justify-center">
          <Loader2 className="animate-spin text-[#29b6f6] mb-3" size={28} />
        </div>
      ) : error ? (
        <div className="flex-1 flex flex-col items-center justify-center text-center px-4">
          <div className="w-12 h-12 bg-[#f43f5e]/10 rounded-full flex items-center justify-center mb-3">
             <span className="text-[#f43f5e] font-bold font-[var(--font-mono)]">!</span>
          </div>
          <p className="text-[#c9d1dc] text-sm">{error}</p>
        </div>
      ) : documents.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center text-center px-4">
          <div className="w-14 h-14 bg-[#161b25] border border-[#242c3a] rounded-2xl flex items-center justify-center mb-4">
             <FileText size={24} className="text-[#6b7a8d]" />
          </div>
          <p className="text-[#f0f4f8] font-bold mb-1 font-[var(--font-heading)]">No Workspaces</p>
          <p className="text-[#6b7a8d] text-xs">Upload a document to begin analysis.</p>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto space-y-3 pr-2 scrollbar-thin">
          {documents.map((doc) => (
            <div
              key={doc.id}
              onClick={() => onDocumentSelect(doc.id)}
              className={`bg-[#161b25] border rounded-xl p-4 cursor-pointer transition-all group relative overflow-hidden ${
                selectedDocumentId === doc.id
                  ? 'border-[#29b6f6] shadow-[0_0_20px_rgba(41,182,246,0.15)] bg-gradient-to-br from-[#161b25] to-[#125585]/10'
                  : 'border-[#242c3a] hover:border-[#1a6fa3] hover:shadow-soft'
              }`}
            >
              {selectedDocumentId === doc.id && (
                 <div className="absolute top-0 left-0 w-1 h-full bg-[#29b6f6]"></div>
              )}
              
              <div className="flex items-start justify-between mb-3 gap-3">
                <h3 className="text-[#f0f4f8] text-sm font-bold line-clamp-2 flex-1 font-[var(--font-heading)] leading-snug group-hover:text-[#29b6f6] transition-colors">
                  {doc.title}
                </h3>
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 transition-colors ${selectedDocumentId === doc.id ? 'bg-[#29b6f6] text-[#050a0e]' : 'bg-[#1e2433] text-[#6b7a8d] group-hover:text-[#29b6f6]'}`}>
                  <ArrowRight size={14} strokeWidth={selectedDocumentId === doc.id ? 3 : 2} />
                </div>
              </div>
              
              <div className="flex items-center justify-between text-[11px] text-[#6b7a8d] font-[var(--font-mono)] border-t border-[#242c3a] pt-3">
                <span>{formatFileSize(doc.fileSize)}</span>
                <span>{formatDate(doc.uploadDate)}</span>
              </div>
              
              <div className="mt-3">
                <span className={`text-[9px] px-2.5 py-1 rounded-full font-bold font-[var(--font-mono)] tracking-wider uppercase border ${
                  doc.status === 'completed' 
                    ? 'bg-[rgba(41,182,246,0.1)] text-[#29b6f6] border-[rgba(41,182,246,0.2)]' 
                    : doc.status === 'processing'
                    ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                    : 'bg-[#f43f5e]/10 text-[#f43f5e] border-[#f43f5e]/20'
                }`}>
                  {doc.status}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}