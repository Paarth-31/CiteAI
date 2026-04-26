/**
 * CiteAI API client
 *
 * Central module for all HTTP communication with the Flask backend.
 * Every component imports from here — no bare fetch() calls anywhere else.
 *
 * Environment variable required in .env.local:
 *   NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
 */

// ── Base URL ─────────────────────────────────────────────────────────────────

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, '') ||
  'http://127.0.0.1:8000';

// ── Token helpers ─────────────────────────────────────────────────────────────

export function getAccessToken(): string | null {
  if (typeof window === 'undefined') return null;
  return (
    localStorage.getItem('access_token') ||
    sessionStorage.getItem('access_token')
  );
}

export function getRefreshTokenValue(): string | null {
  if (typeof window === 'undefined') return null;
  return (
    localStorage.getItem('refresh_token') ||
    sessionStorage.getItem('refresh_token')
  );
}

export function moveTokensToSession(): void {
  if (typeof window === 'undefined') return;
  const at = localStorage.getItem('access_token');
  const rt = localStorage.getItem('refresh_token');
  if (at) { sessionStorage.setItem('access_token', at); localStorage.removeItem('access_token'); }
  if (rt) { sessionStorage.setItem('refresh_token', rt); localStorage.removeItem('refresh_token'); }
}

export function storeTokens(
  accessToken: string,
  refreshToken: string,
  rememberMe: boolean,
): void {
  const storage = rememberMe ? localStorage : sessionStorage;
  storage.setItem('access_token', accessToken);
  storage.setItem('refresh_token', refreshToken);
}

export function clearTokens(): void {
  ['access_token', 'refresh_token'].forEach(k => {
    localStorage.removeItem(k);
    sessionStorage.removeItem(k);
  });
}

// ── Core fetch wrapper ────────────────────────────────────────────────────────

/**
 * Typed fetch wrapper. Automatically:
 *  - Prepends NEXT_PUBLIC_API_BASE_URL to every path
 *  - Attaches Authorization: Bearer <token> header
 *  - Sets Content-Type: application/json unless FormData body
 *  - Throws a readable Error on non-2xx responses
 */
export async function apiFetch<T = unknown>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getAccessToken();

  const headers = new Headers(options.headers ?? {});

  if (token) headers.set('Authorization', `Bearer ${token}`);

  // Don't set Content-Type for FormData — browser sets it with boundary
  if (!(options.body instanceof FormData)) {
    if (!headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }
  }

  const url = path.startsWith('http') ? path : `${API_BASE}${path}`;

  const res = await fetch(url, { ...options, headers });

  if (!res.ok) {
    let message = `HTTP ${res.status}`;
    try {
      const errBody = await res.json();
      message = errBody.error || errBody.message || message;
    } catch {
      // non-JSON error body
    }
    throw new Error(message);
  }

  // 204 No Content
  if (res.status === 204) return undefined as T;

  return res.json() as Promise<T>;
}

// ── Auth ─────────────────────────────────────────────────────────────────────

export interface UserResponse {
  user: { id: string; name: string; email: string };
}

export interface LoginResponse extends UserResponse {
  accessToken: string;
  refreshToken: string;
}

export async function apiLogin(
  email: string,
  password: string,
): Promise<LoginResponse> {
  return apiFetch<LoginResponse>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
}

export async function apiRegister(
  name: string,
  email: string,
  password: string,
): Promise<UserResponse> {
  return apiFetch<UserResponse>('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify({ name, email, password }),
  });
}

export async function apiLogout(): Promise<void> {
  await apiFetch('/api/auth/logout', { method: 'POST' });
}

export async function apiFetchCurrentUser(): Promise<UserResponse> {
  return apiFetch<UserResponse>('/api/auth/me');
}

export async function apiRefreshAccessToken(): Promise<string | null> {
  const refreshToken = getRefreshTokenValue();
  if (!refreshToken) return null;
  try {
    const data = await apiFetch<{ accessToken: string }>('/api/auth/refresh', {
      method: 'POST',
      headers: { Authorization: `Bearer ${refreshToken}` },
    });
    return data.accessToken;
  } catch {
    return null;
  }
}

// ── Documents ─────────────────────────────────────────────────────────────────

export interface Document {
  id: string;
  title: string;
  fileUrl: string;
  fileSize: number;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  uploadDate: string;
  createdAt: string;
  updatedAt: string;
  userId: string;
  // populated on GET /api/documents/<id>
  citations?: Citation[];
  hasOcrText?: boolean;
  hasCitationGraph?: boolean;
  hasAnalysis?: boolean;
  ocrMetadata?: {
    citations: string[];
    articles: string[];
    keywords: string[];
  };
}

export async function apiListDocuments(params?: {
  search?: string;
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<Document[]> {
  const qs = new URLSearchParams();
  if (params?.search)  qs.set('search', params.search);
  if (params?.status)  qs.set('status', params.status);
  if (params?.limit)   qs.set('limit', String(params.limit));
  if (params?.offset)  qs.set('offset', String(params.offset));
  const query = qs.toString() ? `?${qs}` : '';
  return apiFetch<Document[]>(`/api/documents${query}`);
}

export async function apiGetDocument(id: string): Promise<{ document: Document }> {
  return apiFetch<{ document: Document }>(`/api/documents/${id}`);
}

export async function apiDeleteDocument(id: string): Promise<void> {
  await apiFetch(`/api/documents/${id}`, { method: 'DELETE' });
}

// ── Citations ─────────────────────────────────────────────────────────────────

export interface Citation {
  id: string;
  documentId: string;
  title: string;
  x: number;
  y: number;
  citations: number;
  year: number | null;
  trsScore: number | null;
  similarityScore: number | null;
  evidenceSpan: string | null;
  sourceModel: string | null;
  createdAt: string;
}

export async function apiListCitations(documentId: string, model?: string): Promise<Citation[]> {
  const qs = model ? `?model=${model}` : '';
  return apiFetch<Citation[]>(`/api/documents/${documentId}/citations${qs}`);
}

export async function apiCreateCitation(
  documentId: string,
  data: Partial<Citation>,
): Promise<{ citation: Citation }> {
  return apiFetch<{ citation: Citation }>(
    `/api/documents/${documentId}/citations`,
    { method: 'POST', body: JSON.stringify(data) },
  );
}

export async function apiUpdateCitation(
  documentId: string,
  citationId: string,
  data: Partial<Citation>,
): Promise<{ citation: Citation }> {
  return apiFetch<{ citation: Citation }>(
    `/api/documents/${documentId}/citations/${citationId}`,
    { method: 'PUT', body: JSON.stringify(data) },
  );
}

export async function apiDeleteCitation(
  documentId: string,
  citationId: string,
): Promise<void> {
  await apiFetch(`/api/documents/${documentId}/citations/${citationId}`, {
    method: 'DELETE',
  });
}

// ── OCR & Processing ──────────────────────────────────────────────────────────

export interface OcrProcessResponse {
  success: boolean;
  already_processed?: boolean;
  ocr_metadata?: {
    citations: string[];
    articles: string[];
    keywords: string[];
  };
}

export async function apiProcessDocument(documentId: string): Promise<OcrProcessResponse> {
  return apiFetch<OcrProcessResponse>(`/api/ocr/process/${documentId}`, {
    method: 'POST',
  });
}

export interface CitationNode {
  id: string;
  title: string;
  x: number;
  y: number;
  citations: number;
  year: number | null;
}

export interface CitationNodesResponse {
  nodes: CitationNode[];
  stats: {
    totalNodes: number;
    filteredNodes: number;
    showingTop: number;
    hasMore: boolean;
  };
}

export async function apiGetCitationNodes(
  documentId: string,
  params?: {
    limit?: number;
    layout?: 'force' | 'tree';
    minCitations?: number;
    year?: string;
  },
): Promise<CitationNodesResponse> {
  const qs = new URLSearchParams();
  if (params?.limit)          qs.set('limit', String(params.limit));
  if (params?.layout)         qs.set('layout', params.layout);
  if (params?.minCitations != null) qs.set('minCitations', String(params.minCitations));
  if (params?.year)           qs.set('year', params.year);
  const query = qs.toString() ? `?${qs}` : '';
  return apiFetch<CitationNodesResponse>(`/api/ocr/citation-nodes/${documentId}${query}`);
}

export async function apiGetCitationGraph(
  documentId: string,
): Promise<{ nodes: CitationNode[]; edges: { source: string; target: string }[] }> {
  return apiFetch(`/api/ocr/citation-graph/${documentId}`);
}

export interface OcrQueryResponse {
  answer: string;
  context_used?: string[];
}

export async function apiQueryDocument(
  documentId: string,
  query: string,
): Promise<OcrQueryResponse> {
  return apiFetch<OcrQueryResponse>(`/api/ocr/query/${documentId}`, {
    method: 'POST',
    body: JSON.stringify({ query }),
  });
}

export interface InternalAnalysisResponse {
  coherence_score: number;
  claims: string[];
  contradictions: string[];
  summary?: string;
}

export async function apiGetInternalAnalysis(
  documentId: string,
  force = false,
): Promise<InternalAnalysisResponse> {
  const qs = force ? '?force=1' : '';
  return apiFetch<InternalAnalysisResponse>(`/api/ocr/internal-analysis/${documentId}${qs}`);
}

// ── Inference (InLegalBERT / BioBERT) ────────────────────────────────────────

export interface ExternalInferenceResultCase {
  case_id: string;
  title: string;
  year: number | null;
  jurisdiction: string;
  similarity_score: number;
  context_fit: number;
  jurisdiction_score: number;
  internal_confidence: number;
  uncertainty: number;
  trs: number | { score: number; factors: Record<string, number> };
  alignment_type: 'supports' | 'contradicts' | 'neutral';
  justification: string;
  spans: {
    target_span: string;
    candidate_span: string;
  };
}

export interface ExternalInferenceResponse {
  target: {
    case_id: string;
    title: string;
    year: number | null;
    jurisdiction: string;
  };
  retrieved_cases: ExternalInferenceResultCase[];
  overall_external_coherence_score: number;
  short_summary: string;
}

/**
 * fetchExternalInference — called by ExternalInferencePanel.tsx
 *
 * Maps to Flask POST /api/inference/similar/<documentId>
 * with body: { model: "legalbert", top_k: N, return_factors: bool }
 *
 * The Flask route returns:
 *   { document_id, top_k, results: { legalbert: { retrieved_cases, ... } } }
 *
 * This function unwraps to the ExternalInferenceResponse shape the panel expects.
 */
export async function fetchExternalInference(
  documentId: string,
  options?: {
    topK?: number;
    factors?: boolean;
    model?: 'legalbert' | 'biobert' | 'both';
    signal?: AbortSignal;
  },
): Promise<ExternalInferenceResponse> {
  const model  = options?.model  ?? 'legalbert';
  const top_k  = options?.topK   ?? 5;
  const return_factors = options?.factors ?? false;

  const raw = await apiFetch<{
    document_id: string;
    top_k: number;
    results: {
      legalbert?: ExternalInferenceResponse;
      biobert?:   ExternalInferenceResponse;
    };
  }>(`/api/inference/similar/${documentId}`, {
    method: 'POST',
    body: JSON.stringify({ model, top_k, return_factors }),
    signal: options?.signal,
  });

  // Unwrap — panel expects ExternalInferenceResponse directly
  const modelKey = model === 'both' ? 'legalbert' : model;
  const result = raw.results[modelKey];
  if (!result) {
    throw new Error(`No results returned for model: ${model}`);
  }
  return result;
}

// ── Chats ─────────────────────────────────────────────────────────────────────

export interface Chat {
  id: string;
  title: string;
  userId: string;
  documentId: string | null;
  createdAt: string;
  updatedAt: string;
  messages?: Message[];
}

export interface Message {
  id: string;
  chatId: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  createdAt: string;
}

export async function apiListChats(): Promise<Chat[]> {
  return apiFetch<Chat[]>('/api/chats');
}

export async function apiCreateChat(
  title: string,
  documentId?: string,
): Promise<{ chat: Chat }> {
  return apiFetch<{ chat: Chat }>('/api/chats', {
    method: 'POST',
    body: JSON.stringify({ title, documentId }),
  });
}

export async function apiGetChat(chatId: string): Promise<{ chat: Chat }> {
  return apiFetch<{ chat: Chat }>(`/api/chats/${chatId}`);
}

export async function apiAddMessage(
  chatId: string,
  role: 'user' | 'assistant',
  content: string,
): Promise<{ message: Message }> {
  return apiFetch<{ message: Message }>(`/api/chats/${chatId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ role, content }),
  });
}


// ── Search ──────────────────────────────────────────────────────────────────

export interface SearchResult {
  id: string;
  slug?: string;
  title: string;
  type: 'baseline' | 'document';
  snippet?: string;
  stats?: Record<string, number>;
  citations?: string[];
  status?: string;
}

export async function apiGlobalSearch(q: string): Promise<{ results: SearchResult[]; count: number }> {
  return apiFetch(`/api/search?q=${encodeURIComponent(q)}`);
}

export async function apiListBaselineCases(): Promise<{
  id: string; slug: string; title: string; stats: Record<string, number>; keywords: string[];
}[]> {
  return apiFetch('/api/search/baseline');
}

export async function apiGetBaselineCase(slug: string) {
  return apiFetch<{
    id: string; slug: string; title: string; full_text: string;
    citations: string[]; articles: string[]; keywords: string[]; stats: Record<string, number>;
  }>(`/api/search/baseline/${slug}`);
}

export async function apiGetBaselineCitationNodes(slug: string) {
  return apiFetch<{
    nodes: CitationNode[]; edges: { source: string; target: string }[];
    total_nodes: number; filtered_nodes: number; showing_top: number; has_more: boolean;
  }>(`/api/search/baseline/${slug}/citation-nodes`);
}

interface CitationNode {
  id: string; title: string; x: number; y: number; citations: number; year: number;
}