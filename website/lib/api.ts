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
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  const accessToken = getAccessToken();
  if (accessToken && !headers.has('Authorization')) headers.set('Authorization', `Bearer ${accessToken}`);

  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload?.error || payload?.message || `Request failed (${response.status})`);
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
