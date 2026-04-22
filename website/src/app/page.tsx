import Navbar from "../components/Navbar";
import UploadBox from "../components/UploadBox";

export default function Home() {
  return (
    <div className="min-h-screen flex flex-col bg-gradient-to-br from-gray-50 to-gray-100">

      <Navbar />

      {/* Main */}
      <main className="flex-1 flex items-center justify-center px-4 bg-[radial-gradient(#e5e7eb_1px,transparent_1px)] [background-size:16px_16px]">
        <UploadBox />
      </main>

      {/* Footer */}
      <footer className="text-center text-sm text-gray-500 py-6 border-t bg-white">
        Contact us: Group 20 
      </footer>

    </div>
  );
}