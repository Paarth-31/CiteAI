import { NextRequest, NextResponse } from 'next/server';

export async function GET(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const { id } = await params;

    if (!id) {
      return NextResponse.json({ error: 'Document ID is required' }, { status: 400 });
    }

    // Fetch the abstract text
    const fetchUrl = `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=${id}&retmode=text&rettype=abstract`;
    
    const fetchRes = await fetch(fetchUrl);
    
    if (!fetchRes.ok) {
        throw new Error('Failed to fetch from PubMed');
    }

    const textData = await fetchRes.text();

    // The textData is plain text. We'll format it with basic HTML paragraphs.
    const formattedHtml = textData
      .split('\n\n')
      .filter((p) => p.trim() !== '')
      .map((p) => `<p>${p.trim()}</p>`)
      .join('');

    return NextResponse.json({
      doc: formattedHtml || '<p>No abstract available for this document.</p>'
    });

  } catch (error: any) {
    console.error('PubMed Document Error:', error);
    return NextResponse.json(
      { error: error.message || 'An error occurred fetching document details' },
      { status: 500 }
    );
  }
}
