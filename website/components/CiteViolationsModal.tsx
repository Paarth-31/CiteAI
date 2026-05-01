"use client"

import React, { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { X, Upload, FileText, Loader2, AlertTriangle, CheckCircle2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

interface CiteViolationsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function CiteViolationsModal({ isOpen, onClose }: CiteViolationsModalProps) {
  const [file, setFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!isOpen || !mounted) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile && selectedFile.type === 'application/pdf') {
      setFile(selectedFile);
      setError(null);
    } else {
      setError('Please select a valid PDF file.');
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const droppedFile = e.dataTransfer.files?.[0];
    if (droppedFile && droppedFile.type === 'application/pdf') {
      setFile(droppedFile);
      setError(null);
    } else {
      setError('Please drop a valid PDF file.');
    }
  };

  const toBase64 = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.readAsDataURL(file);
      reader.onload = () => {
        const result = reader.result as string;
        // Strip the data:application/pdf;base64, prefix
        const base64Data = result.split(',')[1];
        resolve(base64Data);
      };
      reader.onerror = (error) => reject(error);
    });
  };

  const handleAnalyze = async () => {
    if (!file) return;

    setIsLoading(true);
    setError(null);
    setResult(null);

    try {
      const base64Data = await toBase64(file);

      const response = await fetch('/api/cite-violations', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          base64Data,
          mimeType: file.type,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Failed to analyze the document.');
      }

      setResult(data.result);
    } catch (err: any) {
      setError(err.message || 'An unexpected error occurred.');
    } finally {
      setIsLoading(false);
    }
  };

  const resetState = () => {
    setFile(null);
    setResult(null);
    setError(null);
  };

  const modalContent = (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-[#0f1117]/80 backdrop-blur-md">
      <div className="relative w-full max-w-3xl max-h-[90vh] flex flex-col glass-card rounded-2xl border border-[#242c3a] shadow-soft overflow-hidden">
        
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-[#242c3a] bg-[#161b25]/50">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#f43f5e] to-[#9f1239] flex items-center justify-center shadow-[0_0_15px_rgba(244,63,94,0.3)]">
              <AlertTriangle className="text-[#f0f4f8]" size={20} />
            </div>
            <div>
              <h2 className="text-xl font-bold text-[#f0f4f8] tracking-tight font-[var(--font-heading)]">
                Cite Violations
              </h2>
              <p className="text-xs text-[#6b7a8d] font-[var(--font-sans)]">
                Analyze document against Indian established laws
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-[#6b7a8d] hover:text-[#f0f4f8] hover:bg-[#1e2433] p-2 rounded-lg transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 scrollbar-thin scrollbar-thumb-[#242c3a] scrollbar-track-transparent">
          
          {!result && !isLoading && (
            <div className="space-y-6">
              {/* Upload Area */}
              <div 
                className={`border-2 border-dashed rounded-xl p-10 text-center transition-colors ${
                  file ? 'border-[#29b6f6] bg-[#29b6f6]/5' : 'border-[#242c3a] hover:border-[#4b5563] bg-[#161b25]/50'
                }`}
                onDragOver={handleDragOver}
                onDrop={handleDrop}
                onClick={() => !file && fileInputRef.current?.click()}
              >
                <input 
                  type="file" 
                  ref={fileInputRef} 
                  className="hidden" 
                  accept="application/pdf"
                  onChange={handleFileChange}
                />
                
                {file ? (
                  <div className="flex flex-col items-center gap-3">
                    <div className="w-16 h-16 bg-[#1e2433] rounded-full flex items-center justify-center text-[#29b6f6]">
                      <FileText size={32} />
                    </div>
                    <div>
                      <p className="text-[#f0f4f8] font-medium font-[var(--font-sans)]">{file.name}</p>
                      <p className="text-xs text-[#6b7a8d] mt-1 font-[var(--font-mono)]">
                        {(file.size / 1024 / 1024).toFixed(2)} MB
                      </p>
                    </div>
                    <button 
                      onClick={(e) => { e.stopPropagation(); resetState(); }}
                      className="text-sm text-[#f43f5e] hover:underline mt-2 font-[var(--font-sans)]"
                    >
                      Remove File
                    </button>
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-3 cursor-pointer">
                    <div className="w-16 h-16 bg-[#1e2433] rounded-full flex items-center justify-center text-[#6b7a8d]">
                      <Upload size={32} />
                    </div>
                    <div>
                      <p className="text-[#f0f4f8] font-medium font-[var(--font-sans)]">Click to upload or drag and drop</p>
                      <p className="text-sm text-[#6b7a8d] mt-1 font-[var(--font-sans)]">PDF files only (Max 20MB)</p>
                    </div>
                  </div>
                )}
              </div>

              {error && (
                <div className="p-4 rounded-xl bg-[#f43f5e]/10 border border-[#f43f5e]/20 text-[#f43f5e] text-sm flex items-start gap-3">
                  <AlertTriangle size={18} className="shrink-0 mt-0.5" />
                  <p>{error}</p>
                </div>
              )}

              <button
                onClick={handleAnalyze}
                disabled={!file || isLoading}
                className={`w-full py-4 rounded-xl font-bold transition-all ${
                  file && !isLoading
                    ? 'bg-gradient-to-r from-[#29b6f6] to-[#1a6fa3] hover:opacity-90 text-[#050a0e]'
                    : 'bg-[#1e2433] text-[#6b7a8d] cursor-not-allowed'
                }`}
              >
                Analyze Document
              </button>
            </div>
          )}

          {isLoading && (
            <div className="flex flex-col items-center justify-center py-20 space-y-6">
              <div className="relative">
                <div className="w-20 h-20 border-4 border-[#1e2433] rounded-full"></div>
                <div className="w-20 h-20 border-4 border-[#29b6f6] rounded-full border-t-transparent animate-spin absolute top-0 left-0"></div>
                <div className="absolute inset-0 flex items-center justify-center">
                  <Loader2 className="text-[#29b6f6]" size={24} />
                </div>
              </div>
              <div className="text-center">
                <h3 className="text-lg font-bold text-[#f0f4f8] mb-2 font-[var(--font-heading)]">Analyzing Violations...</h3>
                <p className="text-[#6b7a8d] text-sm font-[var(--font-sans)]">
                  Cross-referencing against Indian established laws.
                </p>
              </div>
            </div>
          )}

          {result && !isLoading && (
            <div className="space-y-6 animate-fade-in">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-[#4ade80]">
                  <CheckCircle2 size={18} />
                  <span className="font-medium text-sm">Analysis Complete</span>
                </div>
                <button 
                  onClick={resetState}
                  className="text-xs text-[#29b6f6] hover:underline font-[var(--font-sans)]"
                >
                  Analyze another file
                </button>
              </div>
              
              <div className="prose prose-invert max-w-none prose-p:text-[#c9d1dc] prose-headings:text-[#f0f4f8] prose-headings:font-[var(--font-heading)] prose-a:text-[#29b6f6] prose-strong:text-[#f0f4f8] prose-ul:text-[#c9d1dc]">
                <ReactMarkdown>{result}</ReactMarkdown>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );

  return createPortal(modalContent, document.body);
}
