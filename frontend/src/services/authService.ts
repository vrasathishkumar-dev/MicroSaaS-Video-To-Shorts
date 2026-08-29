import api, { clearAuthTokens, getRefreshToken, setAuthTokens } from '@/services/api';
import type { AuthTokens, User } from '@/types';

/** Payload for POST /auth/register. */
export interface RegisterPayload {
  email: string;
  password: string;
  full_name: string;
}

/** Payload for PUT /auth/me. All fields optional — send only what changed. */
export interface UpdateProfilePayload {
  full_name?: string;
  email?: string;
}

/**
 * Registers a new account. Does not log the user in — callers should
 * follow up with `login()` once registration succeeds.
 */
export async function register(
  email: string,
  password: string,
  fullName: string,
): Promise<User> {
  const payload: RegisterPayload = {
    email,
    password,
    full_name: fullName,
  };
  const { data } = await api.post<User>('/auth/register', payload);
  return data;
}

/**
 * Logs in via the OAuth2 password flow the backend expects: a
 * form-encoded body with `username`/`password` fields (FastAPI's
 * OAuth2PasswordRequestForm), not JSON. Persists the returned token
 * pair via `setAuthTokens` on success.
 */
export async function login(email: string, password: string): Promise<AuthTokens> {
  const params = new URLSearchParams();
  params.append('username', email);
  params.append('password', password);

  const { data } = await api.post<AuthTokens>('/auth/login', params, {
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
  });
  setAuthTokens(data);
  return data;
}

/**
 * Logs the current user out. Best-effort — the backend session is
 * invalidated if reachable, but local tokens are always cleared.
 */
export async function logout(): Promise<void> {
  const refreshToken = getRefreshToken();
  try {
    if (refreshToken) {
      await api.post('/auth/logout', { refresh_token: refreshToken });
    }
  } catch {
    // Best-effort logout: ignore server network errors
  } finally {
    clearAuthTokens();
  }
}

/** Fetches the currently authenticated user's profile. */
export async function getMe(): Promise<User> {
  const { data } = await api.get<User>('/auth/me');
  return data;
}

/** Updates the currently authenticated user's profile. */
export async function updateProfile(payload: UpdateProfilePayload): Promise<User> {
  const { data } = await api.put<User>('/auth/me', payload);
  return data;
}
