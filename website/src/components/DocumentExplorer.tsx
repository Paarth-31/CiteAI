"use client"

import React, { useEffect, useState } from 'react';
import { apiFetch } from '../lib/api';
import { FileText } from 'lucide-react';

interface Document {
  id: string;
  title: string;
  created_at: string;
}

interface DocumentExplorerProps {
  onDocumentSelect: (id: string) => void;
  selectedDocumentId: string | null;
}

export default function DocumentExplorer({ onDocumentSelect, selectedDocumentId }: DocumentExplorerProps) {
  const [documents, setDocuments] = useState<Document[]>([]);

  // useEffect(() => {
  //   apiFetch<Document[]>('/api/documents').then(setDocuments).catch(console.error);
  // }, []);

  useEffect(() => {
  // TEMP: dummy data instead of backend
  setDocuments([
    {
      id: "1",
      title: "Sample Legal Document",
      created_at: new Date().toISOString()
    },
    {
      id: "2",
      title: "Privacy Case Study",
      created_at: new Date().toISOString()
    }
  ]);
}, []);

  return (
    <div className="bg-white border border-neutral-200 rounded-lg p-4 h-full overflow-y-auto">
      <h3 className="font-medium text-sm mb-4">Uploaded Documents</h3>
      <div className="space-y-2">
        {documents.map((doc) => (
          <button
            key={doc.id}
            onClick={() => onDocumentSelect(doc.id)}
            className={`w-full text-left p-3 rounded-lg flex items-center gap-3 transition-colors ${
              selectedDocumentId === doc.id ? 'bg-green-50 border border-green-200' : 'hover:bg-neutral-50'
            }`}
          >
            <FileText size={16} className={selectedDocumentId === doc.id ? 'text-green-600' : 'text-neutral-400'} />
            <span className="text-sm truncate">{doc.title}</span>
          </button>
        ))}
      </div>
    </div>
  );
}