"use client";

import { useEffect, useState } from 'react';
import { ExternalLink, FileText, Search } from 'lucide-react';
import { googlePdfSearchUrl, resolveCitationPdf } from '@/lib/citationSources';

export default function CitationSourceLinks({ title }: { title: string }) {
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    resolveCitationPdf(title)
      .then(url => { if (active) setPdfUrl(url); })
      .catch(() => { if (active) setPdfUrl(null); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [title]);

  return (
    <div className="rounded-xl border border-[#29b6f6]/30 bg-[#0f1117]/95 p-3 shadow-xl backdrop-blur-md max-w-xs">
      <p className="text-xs font-semibold text-[#f0f4f8] line-clamp-2 mb-2">{title}</p>
      <div className="flex flex-wrap gap-2 text-xs">
        {pdfUrl ? (
          <a href={pdfUrl} target="_blank" rel="noopener noreferrer"
            className="inline-flex items-center gap-1 rounded-lg bg-[#29b6f6] px-2.5 py-1.5 font-semibold text-[#050a0e]">
            <FileText size={13} /> Open case PDF <ExternalLink size={12} />
          </a>
        ) : (
          <span className="text-[#6b7a8d] py-1.5">{loading ? 'Finding case PDF…' : 'No exact PDF match found'}</span>
        )}
        <a href={googlePdfSearchUrl(title)} target="_blank" rel="noopener noreferrer"
          className="inline-flex items-center gap-1 rounded-lg border border-[#3b4a5e] px-2.5 py-1.5 text-[#c9d1dc] hover:text-white">
          <Search size={13} /> Google PDF search <ExternalLink size={12} />
        </a>
      </div>
    </div>
  );
}
