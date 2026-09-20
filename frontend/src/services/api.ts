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

const BACKEND_BASE_URL = 'http://localhost:8000';

/**
 * Fetches truthful backend readiness and model status.
 * Tries the Vite proxy path (/health) first, falling back to direct backend address if needed.
 */
export async function fetchHealth(): Promise<SystemHealth> {
  let response: Response;
  try {
    response = await fetch('/health');
    if (!response.ok) {
      throw new Error(`Proxy /health returned ${response.status}`);
    }
  } catch {
    // Direct backend fallback
    response = await fetch(`${BACKEND_BASE_URL}/health`);
    if (!response.ok) {
      throw new Error(`Direct /health returned ${response.status}`);
    }
  }

  return response.json();
}

/**
 * Retrieves enrolled biometric speaker profiles from backend SQLite store.
 */
export async function fetchSpeakers(): Promise<SpeakerProfile[]> {
  let response: Response;
  try {
    response = await fetch('/api/speakers');
    if (!response.ok) {
      throw new Error(`Proxy /api/speakers returned ${response.status}`);
    }
  } catch {
    response = await fetch(`${BACKEND_BASE_URL}/api/speakers`);
    if (!response.ok) {
      throw new Error(`Direct /api/speakers returned ${response.status}`);
    }
  }

  return response.json();
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
 * Ensures an active operator session token exists.
 * If not already in localStorage, automatically logs in using the default operator account.
 */
export async function ensureAuthToken(): Promise<string> {
  const cached = getAuthToken();
  if (cached) {
    return cached;
  }

  try {
    let res: Response;
    try {
      res = await fetch('/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: 'analyst@vshield.internal',
          password: 'VShieldSecure2026!',
        }),
      });
    } catch {
      res = await fetch(`${BACKEND_BASE_URL}/api/v1/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: 'analyst@vshield.internal',
          password: 'VShieldSecure2026!',
        }),
      });
    }

    if (res.ok) {
      const data = await res.json();
      if (data.access_token) {
        setAuthToken(data.access_token);
        return data.access_token;
      }
    }
  } catch (err) {
    console.warn('[V-SHIELD Auth] Auto-authentication notice:', err);
  }

  return '';
}
