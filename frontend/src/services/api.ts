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
