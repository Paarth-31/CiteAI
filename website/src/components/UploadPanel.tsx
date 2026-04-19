"use client"

import React, { useRef, useState } from 'react';
import { useAuth } from './contexts/AuthContext';

interface UploadPanelProps {
  onAnalysisComplete: (dummyData: any) => void;
}

export default function UploadPanel({ onAnalysisComplete }: UploadPanelProps) {
  const { user } = useAuth();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [status, setStatus] = useState<'idle' | 'uploading' | 'analyzing'>('idle');

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file && user) {
      // simulating backend processing pipeline
      setStatus('uploading');
      
      setTimeout(() => {
        setStatus('analyzing');
        
        setTimeout(() => {
          setStatus('idle');
          // dummy data to return to the parent page
          onAnalysisComplete({
            nodes: [
              { id: "1", title: "Article 21 of Constitution", citations: 15 },
              { id: "2", title: "K.S. Puttaswamy v. UOI", citations: 42 },
              { id: "3", title: "IT Act Sec 66A", citations: 8 }
            ],
            edges: [
              { source: "2", target: "1" },
              { source: "3", target: "1" }
            ]
          });
        }, 1500); // 1.5s analyzing
      }, 1000); // 1s uploading
    }
  };

  if (!user) {
    return (
      <div className="bg-white shadow-sm rounded-2xl p-8 w-full max-w-md text-center border border-gray-200">
        <h2 className="text-xl font-semibold mb-2">Sign in required</h2>
        <p className="text-gray-500 text-sm">Please sign in to upload documents.</p>
      </div>
    );
  }

  return (
    <div className="bg-white shadow-lg rounded-2xl p-8 w-full max-w-md text-center border border-gray-200">
      <h2 className="text-xl font-semibold mb-2">Analyze Document</h2>
      
      {status === 'idle' ? (
        <>
          <p className="text-gray-500 text-sm mb-6">Upload a PDF to generate a citation graph</p>
          <input type="file" accept=".pdf" ref={inputRef} onChange={handleFileChange} className="hidden" />
          <button
            onClick={() => inputRef.current?.click()}
            className="bg-green-600 text-white px-6 py-2 rounded-lg hover:bg-green-700 transition"
          >
            Select File
          </button>
        </>
      ) : (
        <div className="py-6 flex flex-col items-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-green-600 mb-4"></div>
          <p className="text-sm font-medium text-gray-700">
            {status === 'uploading' ? 'Uploading to server...' : 'Extracting citations...'}
          </p>
        </div>
      )}
    </div>
  );
}