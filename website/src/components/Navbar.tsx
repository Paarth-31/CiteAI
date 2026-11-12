export default function Navbar() {
    return (
      <div className="w-full border-b bg-white/80 backdrop-blur sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-6 py-4 flex justify-between items-center">
          <h1 className="font-semibold text-lg">CiteAI</h1>
          <span className="text-sm text-gray-500">v0.first_eval</span>
        </div>
      </div>
    );
  }