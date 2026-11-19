export function googlePdfSearchUrl(title: string): string {
  return `https://www.google.com/search?q=${encodeURIComponent(`"${title}" filetype:pdf`)}`;
}

function normalizeCaseTitle(value: string): string {
  return value
    .replace(/<[^>]*>/g, ' ')
    .replace(/\bon\s+\d{1,2}\s+[a-z]+\s+\d{4}.*$/i, '')
    .toLowerCase()
    .replace(/\b(?:versus|vs?\.?)(?=\s)/g, 'v')
    .replace(/[^a-z0-9]+/g, ' ')
    .trim()
    .replace(/\s+/g, ' ');
}

export function isMatchingCase(citationTitle: string, resultTitle: string): boolean {
  const citation = normalizeCaseTitle(citationTitle);
  const result = normalizeCaseTitle(resultTitle);
  if (citation.length < 18 || result.length < 18) return false;
  return citation === result || result.startsWith(`${citation} `) || citation.startsWith(`${result} `);
}

export async function resolveCitationPdf(title: string, signal?: AbortSignal): Promise<string | null> {
  const query = title.replace(/\s+v(?:s)?\.?\s+/gi, ' ').slice(0, 160);
  const response = await fetch('/api/indian-kanoon/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ formInput: query, pagenum: 0 }),
    signal,
  });
  if (!response.ok) return null;
  const data = await response.json();
  const docs: Array<{ title?: string; tid?: number | string }> = Array.isArray(data.docs) ? data.docs : [];
  const match = docs.find(doc => doc.title && isMatchingCase(title, doc.title) && /^\d+$/.test(String(doc.tid)));
  return match ? `https://indiankanoon.org/doc/${match.tid}/?type=pdf` : null;
}
