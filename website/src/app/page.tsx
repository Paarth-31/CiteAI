"use client"

import { useState } from "react";
import Navbar from "../components/Navbar";
import UploadBox from "../components/UploadBox";
import DocumentExplorer from "../components/DocumentExplorer";
import CitationGraph from "../components/CitationGraph";

export default function Home() {
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);

  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      <Navbar />

      <main className="flex-1 flex p-6 gap-6">
        {selectedDocId ? (
          // Dashboard View
          <>
            <div className="w-1/4">
              <DocumentExplorer 
                selectedDocumentId={selectedDocId} 
                onDocumentSelect={setSelectedDocId} 
              />
            </div>
            <div className="flex-1">
              <CitationGraph 
                nodes={[]}
                onNodeSelect={(node) => console.log(node)}
                selectedNodeIds={[]}
                onNodePositionUpdate={(id, x, y) => console.log(id, x, y)}
              />
            </div>
          </>
        ) : (
          // Landing View
          <div className="w-full flex items-center justify-center">
            <UploadBox />
          </div>
        )}
      </main>
    </div>
  );
}