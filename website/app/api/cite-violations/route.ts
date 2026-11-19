import { NextRequest, NextResponse } from 'next/server';
import { GoogleGenerativeAI } from '@google/generative-ai';

function apiStatus(error: unknown): number | null {
  if (typeof error !== 'object' || error === null || !('status' in error)) return null;
  const status = error.status;
  return typeof status === 'number' ? status : null;
}

export async function POST(req: NextRequest) {
  try {
    const apiKey = process.env.GEMINI_API_KEY?.trim();
    if (!apiKey) {
      return NextResponse.json(
        { error: 'Gemini API key is not configured. Please add GEMINI_API_KEY to your .env.local file and restart your development server (npm run dev).' },
        { status: 503 }
      );
    }

    const { base64Data, mimeType } = await req.json();

    if (!base64Data || !mimeType) {
      return NextResponse.json(
        { error: 'Missing file data' },
        { status: 400 }
      );
    }

    const genAI = new GoogleGenerativeAI(apiKey);
    const primaryModel = process.env.GEMINI_MODEL?.trim() || 'gemini-2.5-flash';
    const fallbackModel = process.env.GEMINI_FALLBACK_MODEL?.trim() || 'gemini-2.5-flash-lite';
    const models = [...new Set([primaryModel, fallbackModel])];

    const prompt = `
You are an expert legal AI specializing in all established Indian laws.
I am providing you with a document.
Analyze this document thoroughly and identify ANY violations of established Indian laws.

CRITICAL FORMATTING RULES:
You must return highly readable, concise, and scannable Markdown. Do NOT write dense paragraphs or walls of text.

If NO VIOLATIONS are found:
### ✅ No Obvious Violations Found
Provide a maximum 2-sentence summary explaining why.

If VIOLATIONS ARE FOUND:
For each violation, use the following exact structure with bullet points:
*   **Law/Act violated:** [Name of Law]
*   **Description:** [1-sentence summary of the law]
*   **Reason:** [1-2 sentences explaining why the document violates it]

Use double line breaks between different violations to ensure good spacing.
`;

    const parts = [prompt, { inlineData: { data: base64Data, mimeType } }];
    for (const [modelIndex, modelName] of models.entries()) {
      const attempts = modelIndex === 0 ? 2 : 1;
      const model = genAI.getGenerativeModel({ model: modelName }, { timeout: 60_000 });
      for (let attempt = 0; attempt < attempts; attempt++) {
        try {
          const response = await model.generateContent(parts);
          const text = response.response.text();
          if (!text.trim()) throw new Error('Gemini returned an empty report.');
          return NextResponse.json({ result: text });
        } catch (error) {
          if (apiStatus(error) !== 503) throw error;
          console.warn(`Gemini model ${modelName} is temporarily at capacity`);
          if (attempt + 1 < attempts) {
            await new Promise(resolve => setTimeout(resolve, 1_000));
          }
        }
      }
    }

    return NextResponse.json(
      { error: 'Gemini is temporarily busy. Please try again in a few minutes.' },
      { status: 503 },
    );
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : String(error);
    console.error('Error in cite-violations API:', error);
    return NextResponse.json(
      { error: message || 'An error occurred during analysis.' },
      { status: 500 }
    );
  }
}
