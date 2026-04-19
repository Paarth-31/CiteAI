"use client"

import { useState } from "react";
import Navbar from "../components/Navbar";
import UploadBox from "../components/UploadBox";
import DocumentExplorer from "../components/DocumentExplorer";
import CitationGraph from "../components/CitationGraph";
import { AuthProvider } from "../components/contexts/AuthContext";
import AuthModal from "../components/AuthModal";

function Dashboard() {
  // implement graph storing, currently dummy
  const [graphData, setGraphData] = useState<any | null>(null);

  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      <Navbar />
      <AuthModal />

      <main className="flex-1 flex p-6 gap-6">
        {graphData ? (
          // dashboard view shows when we have dummy data
          <>
            <div className="w-1/4">
              <DocumentExplorer 
                selectedDocumentId="dummy-doc-1" 
                onDocumentSelect={() => console.log("Selecting doc...")} 
              />
            </div>
            <div className="flex-1 flex flex-col gap-4">
              <button 
                onClick={() => setGraphData(null)}
                className="self-start text-sm text-gray-500 hover:text-black font-medium"
              >
                &larr; Upload another document
              </button>
              
              <div className="flex-1 bg-white border border-gray-200 rounded-xl overflow-hidden">
                <CitationGraph 
                  data={graphData} // pass data when backend
                />
              </div>
            </div>
          </>
        ) : (
          // Landing View
          <div className="w-full flex items-center justify-center">
            <UploadBox onUploadComplete={setGraphData} />
          </div>
        )}
      </main>
    </div>
  );
}

export default function Home() {
  return <Dashboard />;
}