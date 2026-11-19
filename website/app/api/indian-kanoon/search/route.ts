import { NextRequest, NextResponse } from 'next/server';

const INDIAN_KANOON_API_TOKEN = 'd393d383ef7d0004e37c866904d87f8273026a16';

export async function POST(request: NextRequest) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { error: 'A JSON search request body is required' },
      { status: 400 }
    );
  }
  if (!body || typeof body !== 'object' || Array.isArray(body)) {
    return NextResponse.json({ error: 'Invalid search request' }, { status: 400 });
  }
  const { formInput, pagenum = 0 } = body as { formInput?: unknown; pagenum?: unknown };
  if (typeof formInput !== 'string' || !formInput.trim()) {
    return NextResponse.json({ error: 'Search query (formInput) is required' }, { status: 400 });
  }
  if (!Number.isInteger(pagenum) || Number(pagenum) < 0) {
    return NextResponse.json({ error: 'pagenum must be a non-negative integer' }, { status: 400 });
  }
  try {
    // Make POST request to Indian Kanoon API
    const searchUrl = `https://api.indiankanoon.org/search/?formInput=${encodeURIComponent(formInput.trim())}&pagenum=${pagenum}`;
    
    const response = await fetch(searchUrl, {
      method: 'POST',
      headers: {
        'Authorization': `Token ${INDIAN_KANOON_API_TOKEN}`,
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      console.error('Indian Kanoon API error:', response.status, response.statusText);
      return NextResponse.json(
        { error: `Indian Kanoon API returned ${response.status}` },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Search API error:', error);
    return NextResponse.json(
      { error: 'Failed to perform search' },
      { status: 500 }
    );
  }
}
