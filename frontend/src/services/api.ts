/**
 * V-SHIELD Core REST API Client (SIH 2026).
 * Manages health checks, speaker profiles, and backend communication.
 */

export interface SystemHealth {
  status: 'ok' | 'degraded' | 'error' | string;
  model_loaded: boolean;
  device: string;
  anti_spoof_model: string;
  speaker_verification_loaded: boolean;
  version?: string;
  aasist_loaded?: boolean;
  ecapa_loaded?: boolean;
  enrolled_speakers_count?: number;
  aasist_onnx_loaded?: boolean;
  ecapa_onnx_loaded?: boolean;
  cuda_available?: boolean;
  details?: Record<string, string> | null;
}

export interface SpeakerProfile {
  speaker_id: string;
  name?: string;
  enrolled_at?: number;
}

const CONFIGURED_API_URL = import.meta.env.VITE_API_URL
  ? import.meta.env.VITE_API_URL.replace(/\/+$/, '')
  : '';

export const BACKEND_BASE_URL = CONFIGURED_API_URL || 'http://localhost:8000';

export function getApiUrl(path: string): string {
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  if (CONFIGURED_API_URL) {
    return `${CONFIGURED_API_URL}${cleanPath}`;
  }
  return cleanPath;
}

/**
 * Fetches truthful backend readiness and model status.
 * Prioritizes configured VITE_API_URL or relative Vite proxy path (/health).
 */
export async function fetchHealth(): Promise<SystemHealth> {
  const url = getApiUrl('/health');
  let response: Response;
  try {
    response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Health check returned ${response.status}`);
    }
  } catch (err) {
    if (!CONFIGURED_API_URL) {
      response = await fetch(`${BACKEND_BASE_URL}/health`);
      if (!response.ok) throw err;
    } else {
      throw err;
    }
  }

  return response.json();
}

/**
 * Retrieves enrolled biometric speaker profiles from backend.
 */
export async function fetchSpeakers(): Promise<SpeakerProfile[]> {
  const url = getApiUrl('/api/speakers');
  let response: Response;
  try {
    response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Fetch speakers returned ${response.status}`);
    }
  } catch (err) {
    if (!CONFIGURED_API_URL) {
      response = await fetch(`${BACKEND_BASE_URL}/api/speakers`);
      if (!response.ok) throw err;
    } else {
      throw err;
    }
  }

  return response.json();
}

export interface UserProfile {
  user_id: string;
  username: string;
  name: string;
  role: string;
  picture?: string | null;
}

/**
 * Returns currently stored authentication token from localStorage.
 */
export function getAuthToken(): string | null {
  return localStorage.getItem('vshield_auth_token');
}

/**
 * Persists an operator authentication token.
 */
export function setAuthToken(token: string): void {
  localStorage.setItem('vshield_auth_token', token);
}

/**
 * Clears stored authentication token.
 */
export function removeAuthToken(): void {
  localStorage.removeItem('vshield_auth_token');
}

/**
 * Ensures an active operator session token exists.
 * Returns cached token from localStorage if present.
 */
export async function ensureAuthToken(): Promise<string> {
  return getAuthToken() || '';
}

/**
 * Authenticates user credentials against the V-SHIELD backend.
 */
export async function loginOperator(
  username: string,
  password: string
): Promise<{ access_token: string; user: UserProfile }> {
  const payload = { username, password };
  const url = getApiUrl('/api/v1/auth/login');
  let res: Response;
  try {
    res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  } catch (err) {
    if (!CONFIGURED_API_URL) {
      res = await fetch(`${BACKEND_BASE_URL}/api/v1/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    } else {
      throw err;
    }
  }

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: 'Authentication failed' }));
    throw new Error(errorData.detail || `Login failed (${res.status})`);
  }

  const data = await res.json();
  if (data.access_token) {
    setAuthToken(data.access_token);
  }
  return data;
}

/**
 * Retrieves authenticated operator profile.
 */
export async function fetchCurrentUser(token?: string): Promise<UserProfile> {
  const authToken = token || getAuthToken();
  if (!authToken) {
    throw new Error('unauthenticated');
  }

  const headers = {
    Authorization: `Bearer ${authToken}`,
  };

  const url = getApiUrl('/api/v1/auth/me');
  let res: Response;
  try {
    res = await fetch(url, { headers });
  } catch (err) {
    if (!CONFIGURED_API_URL) {
      res = await fetch(`${BACKEND_BASE_URL}/api/v1/auth/me`, { headers });
    } else {
      throw err;
    }
  }

  if (!res.ok) {
    throw new Error(`Session verification failed (${res.status})`);
  }

  return res.json();
}

/**
 * Logs out operator and invalidates backend session.
 */
export async function logoutOperator(): Promise<void> {
  removeAuthToken();
  const url = getApiUrl('/api/v1/auth/logout');
  try {
    await fetch(url, { method: 'POST' });
  } catch {
    if (!CONFIGURED_API_URL) {
      try {
        await fetch(`${BACKEND_BASE_URL}/api/v1/auth/logout`, { method: 'POST' });
      } catch {
        // Local session was already cleared
      }
    }
  }
}

