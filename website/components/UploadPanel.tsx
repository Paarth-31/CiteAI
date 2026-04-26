"use client"

import React, { useState, useRef } from 'react';
import { Upload, FileText, Check, AlertCircle, X } from 'lucide-react';
import { useAuth } from '@/components/contexts/AuthContext';
import { apiFetch } from '@/lib/api';

interface UploadPanelProps {
  onUploadComplete?: (documentId: string) => void;
  onClose?: () => void;
}

export default function UploadPanel({ onUploadComplete, onClose }: UploadPanelProps) {
  const { user, isLoading: authLoading, showAuthModal } = useAuth();
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisStep, setAnalysisStep] = useState<'extracting' | 'analyzing' | 'validating' | 'complete'>('extracting');
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (authLoading) {
    return (
      <div className="w-full max-w-2xl mx-auto">
        <div className="glass-card rounded-3xl p-8 sm:p-12 text-center border border-[#242c3a] shadow-soft">
          <div className="w-12 h-12 border-2 border-[#242c3a] border-t-[#29b6f6] rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-[#6b7a8d] font-[var(--font-mono)] text-sm tracking-widest">LOADING WORKSPACE...</p>
        </div>
      </div>
    );
  }

  // Require sign-in to upload
  if (!user) {
    return (
      <div className="w-full max-w-2xl mx-auto">
        <div className="glass-card rounded-3xl p-8 sm:p-12 text-center border border-[#242c3a] shadow-soft">
          <div className="w-16 h-16 bg-[#161b25] border border-[#242c3a] rounded-2xl flex items-center justify-center mx-auto mb-6 shadow-inner">
            <Upload className="text-[#29b6f6]" size={28} />
          </div>
          <h2 className="text-2xl sm:text-3xl font-bold text-[#f0f4f8] mb-3 tracking-tight font-[var(--font-heading)]">
            Sign In Required
          </h2>
          <p className="text-[#6b7a8d] mb-8 font-[var(--font-sans)] leading-relaxed">
            Please sign in to securely upload and map your source documents.
          </p>
          <button
            onClick={() => showAuthModal('signIn')}
            className="bg-[#29b6f6] hover:bg-[#03a9f4] text-[#050a0e] font-bold px-8 py-3.5 rounded-xl transition-all inline-flex items-center gap-2 shadow-[0_0_15px_rgba(41,182,246,0.25)] font-[var(--font-heading)]"
          >
            Sign In To Continue
          </button>
        </div>
      </div>
    );
  }

  const handleDragEnter = (e: React.DragEvent) => { e.preventDefault(); e.stopPropagation(); setIsDragging(true); };
  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault(); e.stopPropagation();
    const rect = e.currentTarget.getBoundingClientRect();
    if (e.clientX <= rect.left || e.clientX >= rect.right || e.clientY <= rect.top || e.clientY >= rect.bottom) setIsDragging(false);
  };
  const handleDragOver = (e: React.DragEvent) => { e.preventDefault(); e.stopPropagation(); };
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault(); e.stopPropagation(); setIsDragging(false);
    if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]);
  };
  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) handleFile(e.target.files[0]);
  };
  const handleFile = (file: File) => {
    setError(null); setSuccess(false);
    if (file.type !== 'application/pdf') { setError('Please select a PDF file'); return; }
    if (file.size > 50 * 1024 * 1024) { setError('File size exceeds 50MB limit'); return; }
    setSelectedFile(file);
  };

  const handleUpload = async () => {
    if (!selectedFile || !user) return;
    setIsUploading(true); setError(null); setUploadProgress(0);

    const progressInterval = setInterval(() => {
      setUploadProgress(prev => { if (prev >= 90) { clearInterval(progressInterval); return 90; } return prev + 10; });
    }, 200);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);

      // Step 1: Upload the file
      const response = await apiFetch<{ document: { id: string }; message: string }>(`/api/documents/upload`, {
        method: 'POST',
        body: formData,
      });

      clearInterval(progressInterval);
      setUploadProgress(100);
      setIsUploading(false);
      setIsAnalyzing(true);

      const docId = response.document.id;

      // Step 2: Run OCR + citation graph extraction
      setAnalysisStep('extracting');
      await apiFetch(`/api/ocr/process/${docId}`, { method: 'POST' });

      setAnalysisStep('analyzing');
      await new Promise(r => setTimeout(r, 800));

      setAnalysisStep('validating');
      await new Promise(r => setTimeout(r, 500));

      setAnalysisStep('complete');
      setIsAnalyzing(false);
      setSuccess(true);

      setTimeout(() => {
        if (onUploadComplete) onUploadComplete(docId);
        if (onClose) onClose();
      }, 1200);

    } catch (err) {
      clearInterval(progressInterval);
      console.error('Upload error:', err);
      setError(err instanceof Error ? err.message : 'Upload failed. Please try again.');
      setUploadProgress(0);
      setIsUploading(false);
      setIsAnalyzing(false);
    }
  };

  const handleRemoveFile = () => {
    setSelectedFile(null); setError(null); setSuccess(false); setUploadProgress(0);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  const steps = ['extracting', 'analyzing', 'validating', 'complete'] as const;

  return (
    <div className="w-full max-w-2xl mx-auto">
      <div className="glass-card rounded-3xl p-8 sm:p-12 relative border border-[#242c3a] shadow-soft">
        {onClose && (
          <button onClick={onClose} className="absolute top-5 right-5 p-2 text-[#6b7a8d] hover:text-[#f0f4f8] hover:bg-[#1e2433] rounded-xl transition-colors">
            <X size={20} />
          </button>
        )}

        {!selectedFile ? (
          <div
            onDragEnter={handleDragEnter} onDragLeave={handleDragLeave}
            onDragOver={handleDragOver} onDrop={handleDrop}
            className={`relative border-2 border-dashed rounded-2xl p-8 sm:p-14 transition-all ${
              isDragging ? 'border-[#29b6f6] bg-[rgba(41,182,246,0.05)]' : 'border-[#242c3a] hover:border-[#29b6f6]/50 bg-[#0f1117]/50'
            }`}
          >
            <input ref={fileInputRef} type="file" accept=".pdf" onChange={handleFileInput} className="hidden" />
            <div className="text-center">
              <div className="w-16 h-16 bg-[#161b25] border border-[#242c3a] rounded-2xl flex items-center justify-center mx-auto mb-6 shadow-inner">
                <Upload className="text-[#29b6f6]" size={28} />
              </div>
              <h2 className="text-2xl sm:text-3xl font-bold text-[#f0f4f8] mb-3 tracking-tight font-[var(--font-heading)]">Upload your document</h2>
              <p className="text-[#6b7a8d] text-sm sm:text-base mb-8 max-w-md mx-auto font-[var(--font-sans)] leading-relaxed">
                Drag and drop your PDF here, or click the button below to browse files.
              </p>
              <button onClick={() => fileInputRef.current?.click()}
                className="bg-[#29b6f6] hover:bg-[#03a9f4] text-[#050a0e] font-bold px-6 py-3 rounded-xl transition-all inline-flex items-center gap-2 shadow-[0_0_15px_rgba(41,182,246,0.25)] font-[var(--font-heading)]">
                <FileText size={18} /> Choose File
              </button>
              <p className="text-[#6b7a8d] font-[var(--font-mono)] text-xs mt-8 tracking-widest uppercase font-bold">PDF only • Max 50MB</p>
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            <div className="text-center">
              <h2 className="text-2xl font-bold text-[#f0f4f8] mb-2 tracking-tight font-[var(--font-heading)]">
                {success ? 'Upload Complete!' : isAnalyzing ? 'Analyzing Document...' : isUploading ? 'Uploading...' : 'Ready to Upload'}
              </h2>
              <p className="text-[#6b7a8d] text-sm font-[var(--font-sans)]">
                {success ? 'Document uploaded and analyzed successfully.' : isAnalyzing ? 'AI is mapping citation relationships.' : isUploading ? 'Uploading securely...' : 'Review your file before uploading.'}
              </p>
            </div>

            <div className="bg-[#0b0e15] border border-[#242c3a] rounded-2xl p-5 shadow-inner">
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 bg-[rgba(41,182,246,0.1)] rounded-xl flex items-center justify-center shrink-0 border border-[rgba(41,182,246,0.2)]">
                  <FileText className="text-[#29b6f6]" size={22} />
                </div>
                <div className="flex-1 min-w-0 pt-1">
                  <h3 className="text-[#f0f4f8] font-bold text-sm mb-1.5 truncate font-[var(--font-heading)]">{selectedFile.name}</h3>
                  <p className="text-[#6b7a8d] text-xs font-bold font-[var(--font-mono)] tracking-wider">{formatFileSize(selectedFile.size)}</p>
                </div>
                {!isUploading && !success && !isAnalyzing && (
                  <button onClick={handleRemoveFile} className="p-2 text-[#6b7a8d] hover:text-[#f43f5e] hover:bg-[#f43f5e]/10 rounded-xl transition-colors">
                    <X size={18} />
                  </button>
                )}
              </div>

              {isUploading && (
                <div className="mt-5">
                  <div className="w-full bg-[#1e2433] rounded-full h-2 overflow-hidden border border-[#242c3a]">
                    <div className="bg-[#29b6f6] h-full transition-all duration-300 ease-out shadow-[0_0_10px_rgba(41,182,246,0.5)]" style={{ width: `${uploadProgress}%` }} />
                  </div>
                  <div className="flex justify-between mt-2">
                    <p className="text-[10px] font-[var(--font-mono)] font-bold text-[#6b7a8d] tracking-widest uppercase">Uploading</p>
                    <p className="text-[10px] font-[var(--font-mono)] font-bold text-[#29b6f6]">{uploadProgress}%</p>
                  </div>
                </div>
              )}

              {isAnalyzing && (
                <div className="mt-6 space-y-3">
                  {steps.map((step) => {
                    const currentIdx = steps.indexOf(analysisStep);
                    const stepIdx = steps.indexOf(step);
                    const isDone = stepIdx < currentIdx || analysisStep === 'complete';
                    const isCurrent = step === analysisStep;
                    return (
                      <div key={step} className={`flex items-center gap-4 p-3 rounded-xl transition-all ${isCurrent ? 'bg-[rgba(41,182,246,0.05)] border border-[rgba(41,182,246,0.15)]' : 'border border-transparent'}`}>
                        <div className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 ${isDone ? 'bg-[#29b6f6] shadow-[0_0_10px_rgba(41,182,246,0.3)]' : isCurrent ? 'bg-[rgba(41,182,246,0.2)]' : 'bg-[#1e2433]'}`}>
                          {isDone ? <Check size={12} strokeWidth={3} className="text-[#050a0e]" /> :
                           isCurrent ? <div className="w-2.5 h-2.5 bg-[#29b6f6] rounded-full animate-ping" /> :
                           <div className="w-2 h-2 bg-[#6b7a8d] rounded-full" />}
                        </div>
                        <span className={`text-xs font-bold font-[var(--font-sans)] ${isCurrent ? 'text-[#f0f4f8]' : isDone ? 'text-[#c9d1dc]' : 'text-[#6b7a8d]'}`}>
                          {step === 'extracting' && 'Extracting text via OCR'}
                          {step === 'analyzing' && 'Building citation graph'}
                          {step === 'validating' && 'Validating sources'}
                          {step === 'complete' && 'Analysis complete!'}
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}

              {success && (
                <div className="mt-5 flex items-center gap-3 text-[#29b6f6] bg-[rgba(41,182,246,0.1)] border border-[rgba(41,182,246,0.2)] px-4 py-3.5 rounded-xl">
                  <Check size={18} strokeWidth={2.5} />
                  <span className="text-sm font-bold font-[var(--font-sans)]">Document uploaded and mapped successfully.</span>
                </div>
              )}
            </div>

            {error && (
              <div className="flex items-start gap-3 text-[#f43f5e] bg-[#f43f5e]/10 border border-[#f43f5e]/20 px-4 py-3.5 rounded-xl">
                <AlertCircle size={18} className="shrink-0 mt-0.5" />
                <span className="text-sm font-bold font-[var(--font-sans)]">{error}</span>
              </div>
            )}

            {!isUploading && !success && !isAnalyzing && (
              <div className="flex flex-col sm:flex-row gap-4 pt-2">
                <button onClick={handleRemoveFile} className="flex-1 bg-transparent hover:bg-[#1e2433] text-[#f0f4f8] font-bold px-6 py-3.5 rounded-xl transition-all border border-[#242c3a] text-sm font-[var(--font-heading)]">Cancel</button>
                <button onClick={handleUpload} className="flex-1 btn-primary justify-center py-3.5 text-sm">Confirm Upload</button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}