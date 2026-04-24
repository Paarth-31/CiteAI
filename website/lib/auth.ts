/**
 * Auth helpers used by AuthContext.tsx
 *
 * These are thin wrappers over the api.ts functions that also handle
 * token storage so AuthContext stays focused on React state.
 */
import {
  apiLogin,
  apiRegister,
  apiLogout,
  apiFetchCurrentUser,
  apiRefreshAccessToken,
  storeTokens,
  clearTokens,
  type UserResponse,
  type LoginResponse,
} from './api';

export async function login(
  email: string,
  password: string,
  rememberMe = false,
): Promise<LoginResponse> {
  const data = await apiLogin(email, password);
  storeTokens(data.accessToken, data.refreshToken, rememberMe);
  return data;
}

export async function register(
  name: string,
  email: string,
  password: string,
): Promise<UserResponse> {
  return apiRegister(name, email, password);
}

export async function logout(): Promise<void> {
  try {
    await apiLogout();
  } finally {
    clearTokens();
  }
}

export async function fetchCurrentUser(): Promise<UserResponse> {
  return apiFetchCurrentUser();
}

export async function refreshAccessToken(): Promise<string | null> {
  const newToken = await apiRefreshAccessToken();
  if (newToken) {
    // Store the new access token wherever the current one lives
    const inLocal = !!localStorage.getItem('access_token');
    if (inLocal) {
      localStorage.setItem('access_token', newToken);
    } else {
      sessionStorage.setItem('access_token', newToken);
    }
  }
  return newToken;
}
