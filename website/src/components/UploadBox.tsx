"use client"

import { useRef, useState } from "react";

export default function UploadBox() {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);

  const handleClick = () => {
    inputRef.current?.click();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setFileName(file.name);
    }
  };

  return (
    <div className="bg-white shadow-lg rounded-2xl p-8 w-full max-w-md text-center border">
      <h2 className="text-xl font-semibold mb-2">
        Start by uploading
      </h2>

      <p className="text-gray-500 text-sm mb-6">
        Upload a legal document to begin analysis
      </p>

      <input
        type="file"
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

      {fileName && (
        <p className="mt-4 text-sm text-green-600">
          Selected: {fileName}
        </p>
      )}

      <p className="text-xs text-gray-400 mt-6">
        Dummy backend
      </p>
    </div>
  );
}