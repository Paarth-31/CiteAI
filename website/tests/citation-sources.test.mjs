import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import ts from 'typescript';

const source = readFileSync(new URL('../lib/citationSources.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
const { googlePdfSearchUrl, isMatchingCase, resolveCitationPdf } =
  await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);

test('only a matching case receives the direct PDF link', async () => {
  const title = 'Madhav Hayawadanrao Hoskot v. State of Maharashtra';
  assert.equal(isMatchingCase(title, 'Madhav Hayawadanrao Hoskot vs State Of Maharashtra on 17 August, 1978'), true);
  assert.equal(isMatchingCase(title, 'Madhav Hayawadanrao Hoskot vs State Of Orissa on 17 August, 1978'), false);
  assert.match(googlePdfSearchUrl(title), /^https:\/\/www\.google\.com\/search\?q=/);

  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (_url, options) => {
    assert.match(JSON.parse(options.body).formInput, /Madhav Hayawadanrao Hoskot/);
    return {
      ok: true,
      json: async () => ({ docs: [
        { title: 'Madhav Hayawadanrao Hoskot vs State Of Orissa', tid: 1 },
        { title: 'Madhav Hayawadanrao Hoskot vs State Of Maharashtra on 17 August, 1978', tid: 513169 },
      ] }),
    };
  };
  try {
    assert.equal(await resolveCitationPdf(title), 'https://indiankanoon.org/doc/513169/?type=pdf');
  } finally {
    globalThis.fetch = originalFetch;
  }
});
