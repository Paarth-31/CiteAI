import { NextRequest, NextResponse } from 'next/server';

export async function POST(req: NextRequest) {
  try {
    const { formInput, pagenum = 0 } = await req.json();

    if (!formInput) {
      return NextResponse.json({ error: 'Search query is required' }, { status: 400 });
    }

    const retmax = 10;
    const retstart = pagenum * retmax;

    // 1. Search for PMIDs
    const searchUrl = `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=${encodeURIComponent(formInput)}&retmode=json&retmax=${retmax}&retstart=${retstart}`;
    
    const searchRes = await fetch(searchUrl);
    const searchData = await searchRes.json();
    
    const idList = searchData.esearchresult?.idlist || [];
    
    if (idList.length === 0) {
      return NextResponse.json({
        docs: [],
        found: "0",
        categories: []
      });
    }

    // 2. Fetch summaries for the PMIDs
    const summaryUrl = `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id=${idList.join(',')}&retmode=json`;
    const summaryRes = await fetch(summaryUrl);
    const summaryData = await summaryRes.json();

    const uids = summaryData.result?.uids || [];
    
    // 3. Map to SearchResult format expected by frontend
    const docs = uids.map((uid: string) => {
      const item = summaryData.result[uid];
      
      const authors = item.authors ? item.authors.map((a: any) => a.name).join(', ') : 'Unknown Author';
      
      return {
        tid: uid, // Use PMID as tid
        title: item.title,
        headline: item.source || 'No abstract available', 
        docsource: item.source || 'PubMed',
        publishdate: item.pubdate,
        author: authors,
        numcites: item.pmcrefcount || 0,
        citation: `PMID: ${uid}`,
      };
    });

    return NextResponse.json({
      docs,
      found: searchData.esearchresult.count || "0",
      categories: [
        ["Database", [{ value: "PubMed", formInput: "PubMed", selected: true }]]
      ]
    });

  } catch (error: any) {
    console.error('PubMed Search Error:', error);
    return NextResponse.json(
      { error: error.message || 'An error occurred during search' },
      { status: 500 }
    );
  }
}
