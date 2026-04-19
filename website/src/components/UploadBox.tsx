"use client"

import { useRef, useState } from "react";
import { useAuth } from "./contexts/AuthContext";

interface UploadBoxProps {
  onUploadComplete: (dummyData: any) => void;
}

export default function UploadBox({ onUploadComplete }: UploadBoxProps) {
  const { user } = useAuth();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [status, setStatus] = useState<'idle' | 'uploading' | 'analyzing'>('idle');

  const handleClick = () => {
    inputRef.current?.click();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file && user) {
      // set upload status
      setStatus('uploading');
      
      // simulate network delay for upload
      setTimeout(() => {
        setStatus('analyzing');
        
        // simulate analysis delay, then return dummy data
        setTimeout(() => {
          setStatus('idle');
          onUploadComplete({
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
        }, 1500); 
      }, 1000); 
    }
  };

  if (!user) {
    return (
      <div className="bg-white shadow-lg rounded-2xl p-8 w-full max-w-md text-center border">
        <h2 className="text-xl font-semibold mb-2">Sign in required</h2>
        <p className="text-gray-500 text-sm">Please sign in using the button in the top right to upload a document.</p>
      </div>
    );
  }

  return (
    <div className="bg-white shadow-lg rounded-2xl p-8 w-full max-w-md text-center border">
      <h2 className="text-xl font-semibold mb-2">
        {status === 'idle' ? 'Start by uploading' : 'Processing Document'}
      </h2>

      {status === 'idle' ? (
        <>
          <p className="text-gray-500 text-sm mb-6">
            Upload a legal document to begin analysis
          </p>

          <input
            type="file"
            accept=".pdf"
            ref={inputRef}
            onChange={handleFileChange}
            className="hidden"
          />

          <button
            onClick={handleClick}
            className="bg-black text-white px-6 py-2 rounded-lg hover:bg-gray-800 transition"
          >
            Upload File
          </button>
        </>
      ) : (
        <div className="py-6 flex flex-col items-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-black mb-4"></div>
          <p className="text-sm font-medium text-gray-700">
            {status === 'uploading' ? 'Uploading to server...' : 'Extracting citations...'}
          </p>
        </div>
      )}

      <p className="text-xs text-gray-400 mt-6">
        Dummy backend mode active
      </p>
    </div>
  );
}