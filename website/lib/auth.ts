import {
  apiFetch,
  clearTokens,
  getRefreshTokenValue,
  storeTokens,
  type ApiUser,
} from './api';

interface AuthResponse {
  accessToken: string;
  refreshToken?: string;
  user: ApiUser;
}

export async function register(name: string, email: string, password: string) {
  return apiFetch<{ user: ApiUser }>('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify({ name, email, password }),
  });
}

export async function login(email: string, password: string, remember = true): Promise<AuthResponse> {
  const response = await apiFetch<AuthResponse>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
  storeTokens(response.accessToken, response.refreshToken, remember);
  return response;
}

export async function fetchCurrentUser() {
  return apiFetch<{ user: ApiUser }>('/api/auth/me');
}

export async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = getRefreshTokenValue();
  if (!refreshToken) return null;
  try {
    const response = await apiFetch<{ accessToken: string }>('/api/auth/refresh', {
      method: 'POST',
      headers: { Authorization: `Bearer ${refreshToken}` },
    });
    storeTokens(response.accessToken, refreshToken, typeof window !== 'undefined' && Boolean(localStorage.getItem('refresh_token')));
    return response.accessToken;
  } catch {
    clearTokens();
    return null;
  }
}

export async function logout() {
  try {
    await apiFetch<{ success: boolean }>('/api/auth/logout', { method: 'POST' });
  } finally {
    clearTokens();
  }
}
