export interface ApiUser {
  id: string;
  name: string;
  email: string;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface ExternalInferenceResultCase {
  case_id: string;
  title: string;
  year?: number | null;
  jurisdiction?: string;
  similarity_score: number;
  context_fit: number;
  jurisdiction_score: number;
  internal_confidence: number;
  uncertainty: number;
  trs: number;
  alignment_type?: string;
  justification: string;
  spans: { target_span: string; candidate_span: string };
}

export interface ExternalInferenceResponse {
  document_id?: string;
  top_k?: number;
  source: string;
  retrieved_cases: ExternalInferenceResultCase[];
  overall_external_coherence_score: number;
  short_summary: string;
  cached?: boolean;
}

type InferencePayload = ExternalInferenceResponse | { error: string };

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');

function tokenKey(name: 'access' | 'refresh') {
  return `${name}_token`;
}

export function getAccessToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(tokenKey('access')) ?? sessionStorage.getItem(tokenKey('access'));
}

export function getRefreshTokenValue(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(tokenKey('refresh')) ?? sessionStorage.getItem(tokenKey('refresh'));
}

export function storeTokens(accessToken: string, refreshToken?: string, remember = true) {
  if (typeof window === 'undefined') return;
  const storage = remember ? localStorage : sessionStorage;
  storage.setItem(tokenKey('access'), accessToken);
  if (refreshToken) storage.setItem(tokenKey('refresh'), refreshToken);
  const other = remember ? sessionStorage : localStorage;
  other.removeItem(tokenKey('access'));
  if (refreshToken) other.removeItem(tokenKey('refresh'));
}

export function moveTokensToSession() {
  if (typeof window === 'undefined') return;
  const access = localStorage.getItem(tokenKey('access'));
  const refresh = localStorage.getItem(tokenKey('refresh'));
  if (access) sessionStorage.setItem(tokenKey('access'), access);
  if (refresh) sessionStorage.setItem(tokenKey('refresh'), refresh);
  localStorage.removeItem(tokenKey('access'));
  localStorage.removeItem(tokenKey('refresh'));
}

export function clearTokens() {
  if (typeof window === 'undefined') return;
  for (const storage of [localStorage, sessionStorage]) {
    storage.removeItem(tokenKey('access'));
    storage.removeItem(tokenKey('refresh'));
  }
  window.dispatchEvent(new Event('citeai:session-expired'));
}

async function fetchWithTimeout(path: string, init: RequestInit): Promise<Response> {
  const controller = new AbortController();
  const abort = () => controller.abort(init.signal?.reason);
  if (init.signal?.aborted) abort();
  else init.signal?.addEventListener('abort', abort, { once: true });
  const longRequest = /\/api\/(ocr|inference)\//.test(path) || path.endsWith('/add-to-db');
  const timer = setTimeout(() => controller.abort(new DOMException('Request timed out. Please retry.', 'TimeoutError')), longRequest ? 300000 : 20000);
  try {
    return await fetch(`${API_BASE_URL}${path}`, { ...init, signal: controller.signal });
  } catch (error) {
    if (error instanceof TypeError) throw new Error('Cannot reach the backend. Check that Flask is running and retry.');
    throw error;
  } finally {
    clearTimeout(timer);
    init.signal?.removeEventListener('abort', abort);
  }
}

let refreshInFlight: Promise<string | null> | null = null;

async function renewAccessToken(): Promise<string | null> {
  if (refreshInFlight) return refreshInFlight;
  const refreshToken = getRefreshTokenValue();
  if (!refreshToken) return null;
  refreshInFlight = (async () => {
    const response = await fetchWithTimeout('/api/auth/refresh', {
      method: 'POST', headers: { Authorization: `Bearer ${refreshToken}` },
    });
    if (response.status === 401 || response.status === 422) {
      if (getRefreshTokenValue() === refreshToken) clearTokens();
      return null;
    }
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.error || body.msg || 'Session renewal failed. Please retry.');
    if (typeof body.accessToken !== 'string' || !body.accessToken) throw new Error('Invalid session renewal response.');
    // A logout or another login during the request must not resurrect this session.
    if (getRefreshTokenValue() !== refreshToken) return null;
    storeTokens(body.accessToken, refreshToken, Boolean(localStorage.getItem('refresh_token')));
    return body.accessToken as string;
  })().finally(() => { refreshInFlight = null; });
  return refreshInFlight;
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  const accessToken = getAccessToken();
  if (accessToken && !headers.has('Authorization')) headers.set('Authorization', `Bearer ${accessToken}`);

  let response = await fetchWithTimeout(path, { ...init, headers });
  const canRefresh = !new Headers(init.headers).has('Authorization') && !/^\/api\/auth\/(login|register|refresh|logout)$/.test(path);
  if (response.status === 401 && canRefresh && !init.signal?.aborted) {
    // Another simultaneous request may already have renewed the token.
    const currentToken = getAccessToken();
    const renewed = currentToken && currentToken !== accessToken ? currentToken : await renewAccessToken();
    if (renewed) {
      headers.set('Authorization', `Bearer ${renewed}`);
      response = await fetchWithTimeout(path, { ...init, headers });
    } else {
      throw new Error('Your session has expired. Please sign in again.');
    }
  }
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload?.error || payload?.message || payload?.msg || `Request failed (${response.status})`);
  }
  return payload as T;
}

export async function fetchExternalInference(
  documentId: string,
  options: { topK: number; signal?: AbortSignal; force?: boolean },
): Promise<ExternalInferenceResponse> {
  const response = await apiFetch<{
    document_id: string;
    top_k: number;
    results: { legal?: InferencePayload };
  }>(`/api/inference/similar/${documentId}`, {
    method: 'POST',
    signal: options.signal,
    body: JSON.stringify({ top_k: options.topK, force: Boolean(options.force) }),
  });
  const legal = response.results?.legal;
  if (!legal || 'error' in legal) {
    throw new Error((legal as { error?: string } | undefined)?.error || 'Inference did not return a legal result');
  }
  return { ...legal, document_id: response.document_id, top_k: response.top_k };
}

export { API_BASE_URL };
