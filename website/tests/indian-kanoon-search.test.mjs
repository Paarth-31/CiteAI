import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import ts from 'typescript';

const route = readFileSync(new URL('../app/api/indian-kanoon/search/route.ts', import.meta.url), 'utf8')
  .replace("import { NextRequest, NextResponse } from 'next/server';",
    'const NextResponse = { json: (body, options = {}) => ({ body, status: options.status ?? 200 }) };');
const compiled = ts.transpileModule(route, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
const { POST } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);

test('empty or incomplete JSON is a client error without an upstream search', async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = () => { throw new Error('Upstream should not be called'); };
  try {
    const response = await POST({ json: async () => { throw new SyntaxError('Unexpected end of JSON input'); } });
    assert.equal(response.status, 400);
    assert.match(response.body.error, /JSON search request body is required/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('valid search JSON still reaches the upstream API', async () => {
  const originalFetch = globalThis.fetch;
  let requestedUrl = '';
  globalThis.fetch = async url => {
    requestedUrl = String(url);
    return { ok: true, json: async () => ({ docs: [{ tid: 513169 }] }) };
  };
  try {
    const response = await POST({ json: async () => ({ formInput: 'Madhav Hoskot', pagenum: 0 }) });
    assert.equal(response.status, 200);
    assert.equal(response.body.docs[0].tid, 513169);
    assert.match(requestedUrl, /formInput=Madhav%20Hoskot/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
