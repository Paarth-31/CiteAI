import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';

function storage() {
  const values = new Map();
  return { getItem: (key) => values.get(key) ?? null, setItem: (key, value) => values.set(key, value), removeItem: (key) => values.delete(key) };
}

function loadClient(fetch) {
  const localStorage = storage();
  const sessionStorage = storage();
  const events = [];
  const context = {
    exports: {}, process: { env: {} }, localStorage, sessionStorage,
    window: { dispatchEvent: (event) => events.push(event.type) },
    Headers, FormData, AbortController, DOMException, Event, setTimeout, clearTimeout,
    fetch,
  };
  const source = readFileSync(new URL('../lib/api.ts', import.meta.url), 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } });
  vm.runInNewContext(compiled.outputText, context);
  context.exports.storeTokens('expired-access', 'valid-refresh', false);
  return { ...context.exports, localStorage, sessionStorage, events };
}

test('concurrent expired requests share a refresh and replay with the new token', async () => {
  let refreshes = 0;
  const client = loadClient(async (url, init) => {
    const auth = new Headers(init.headers).get('Authorization');
    if (url.endsWith('/api/auth/refresh')) {
      refreshes++;
      assert.equal(auth, 'Bearer valid-refresh');
      await new Promise((resolve) => setTimeout(resolve, 10));
      return Response.json({ accessToken: 'new-access' });
    }
    return auth === 'Bearer new-access' ? Response.json({ ok: true }) : Response.json({ msg: 'Token has expired' }, { status: 401 });
  });
  const results = await Promise.all([client.apiFetch('/api/documents'), client.apiFetch('/api/auth/me')]);
  assert.equal(results.every((result) => result.ok), true);
  assert.equal(refreshes, 1);
  assert.equal(client.sessionStorage.getItem('access_token'), 'new-access');
  assert.equal(client.localStorage.getItem('access_token'), null);
});

test('rejected refresh clears expired credentials and does not replay the operation', async () => {
  let calls = 0;
  const client = loadClient(async () => {
    calls++;
    return Response.json({ msg: 'Token has expired' }, { status: 401 });
  });
  await assert.rejects(client.apiFetch('/api/documents/upload', { method: 'POST', body: new FormData() }), /sign in again/);
  assert.equal(calls, 2);
  assert.equal(client.getAccessToken(), null);
  assert.deepEqual(client.events, ['citeai:session-expired']);
});

test('login errors are returned without attempting refresh', async () => {
  let calls = 0;
  const client = loadClient(async () => {
    calls++;
    return Response.json({ error: 'Invalid credentials' }, { status: 401 });
  });
  await assert.rejects(client.apiFetch('/api/auth/login', { method: 'POST' }), /Invalid credentials/);
  assert.equal(calls, 1);
});
