import { NextRequest, NextResponse } from 'next/server';
import { GoogleGenerativeAI } from '@google/generative-ai';

const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY || '');

export async function POST(req: NextRequest) {
  try {
    if (!process.env.GEMINI_API_KEY) {
      return NextResponse.json(
        { error: 'Gemini API key is not configured. Please add GEMINI_API_KEY to your .env.local file and restart your development server (npm run dev).' },
        { status: 500 }
      );
    }

    const { base64Data, mimeType } = await req.json();

    if (!base64Data || !mimeType) {
      return NextResponse.json(
        { error: 'Missing file data' },
        { status: 400 }
      );
    }

    // Initialize the model (using gemini-flash-latest as requested for fast response)
    const model = genAI.getGenerativeModel({ model: 'gemini-flash-latest' });

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

    const result = await model.generateContent([
      prompt,
      {
        inlineData: {
          data: base64Data,
          mimeType,
        },
      },
    ]);

    const response = await result.response;
    const text = response.text();

    return NextResponse.json({ result: text });
  } catch (error: any) {
    console.error('Error in cite-violations API:', error);
    return NextResponse.json(
      { error: error.message || 'An error occurred during analysis.' },
      { status: 500 }
    );
  }
}
