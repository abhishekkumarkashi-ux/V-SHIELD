import { useState, useEffect, useRef, useCallback } from 'react';

export interface TelemetryMetrics {
  spoof_probability: number;
  speaker_similarity: number | null;
  speaker_status?: 'VERIFIED' | 'MISMATCH' | 'EVALUATING' | 'NO_VOICEPRINT' | string;
  buffer_energy_rms: number;
  vad_speech_ratio?: number;
  latency_ms?: number;
}

export interface TelemetryPacket {
  timestamp: number;
  risk_score: number;
  classification: 'LOW_RISK' | 'MEDIUM_RISK' | 'HIGH_RISK';
  metrics: TelemetryMetrics;
  recommended_action:
    | 'ALLOW_CALL'
    | 'MONITOR'
    | 'FLAG_OPERATOR_VERIFICATION'
    | 'STEP_UP_AUTH'
    | 'TRIGGER_MFA_CALLBACK'
    | 'QUARANTINE_TRANSACTION'
    | 'TERMINATE_AND_ALERT';
  status?: 'success' | 'error';
  pipeline_status?: string;
  speaker_status?: 'VERIFIED' | 'MISMATCH' | 'EVALUATING' | 'NO_VOICEPRINT' | string;
  speaker?: {
    status: string;
    similarity: number | null;
    speaker_id: string | null;
    is_match: boolean;
    has_voiceprint: boolean;
  };
  anti_spoof?: {
    score: number;
  };
  risk?: {
    score: number;
  };
}

export interface ServerAudioMetrics {
  type: 'audio_metrics';
  sample_rate: number;
  samples: number;
  duration_ms: number;
  rms: number;
  peak: number;
  pipeline_status?: string;
  speech_state?: string;
}

export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error';
export type PipelineStatus = 'WAITING_FOR_AUDIO' | 'LISTENING' | 'ANALYZING' | 'ANALYSIS_ERROR' | 'READY' | string;

interface UseVShieldSocketProps {
  url?: string;
  speakerId?: string | null;
  onPacketReceived?: (packet: TelemetryPacket) => void;
}

export function useVShieldSocket({
  url = 'ws://localhost:8000/ws/live-call',
  speakerId = null,
  onPacketReceived,
}: UseVShieldSocketProps = {}) {
  const [status, setStatus] = useState<ConnectionStatus>('disconnected');
  const [pipelineStatus, setPipelineStatus] = useState<PipelineStatus>('READY');
  const [latestPacket, setLatestPacket] = useState<TelemetryPacket | null>(null);
  const [serverAudioMetrics, setServerAudioMetrics] = useState<ServerAudioMetrics | null>(null);
  const [history, setHistory] = useState<TelemetryPacket[]>([]);
  const [lastError, setLastError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);

  const connect = useCallback(() => {
    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
      return;
    }

    setStatus('connecting');
    setLastError(null);
    const wsUrl = new URL(url);
    if (speakerId) {
      wsUrl.searchParams.set('speaker_id', speakerId);
    }

    try {
      const ws = new WebSocket(wsUrl.toString());
      ws.binaryType = 'arraybuffer';

      ws.onopen = () => {
        setStatus('connected');
        setLastError(null);
        console.log('[V-SHIELD WS] Connected to backend telemetry gateway');
        ws.send(JSON.stringify({ type: 'start', speaker_id: speakerId, format: 'float32' }));
      };

      ws.onmessage = (event) => {
        if (typeof event.data === 'string') {
          try {
            const data = JSON.parse(event.data);

            if (data.pipeline_status) {
              setPipelineStatus(data.pipeline_status);
            }

            if (data.type === 'session_started') {
              console.log('[V-SHIELD WS] Session started:', data.session_id);
              setLastError(null);
              setPipelineStatus(data.pipeline_status || 'WAITING_FOR_AUDIO');
              return;
            }
            if (data.type === 'session_stopped') {
              console.log('[V-SHIELD WS] Session stopped:', data.session_id);
              setPipelineStatus(data.pipeline_status || 'READY');
              return;
            }
            if (data.type === 'session_reset') {
              console.log('[V-SHIELD WS] Session reset');
              setLatestPacket(null);
              setHistory([]);
              setPipelineStatus(data.pipeline_status || 'READY');
              return;
            }
            if (
              data.type === 'model_error' ||
              data.type === 'audio_error' ||
              data.type === 'protocol_error' ||
              (data.type === 'analysis' && data.status === 'error')
            ) {
              console.warn('[V-SHIELD WS] Error received from gateway:', data);
              setLastError(data.error || 'Gateway protocol error');
              setPipelineStatus(data.pipeline_status || 'ANALYSIS_ERROR');
              return;
            }
            if (data.type === 'audio_metrics') {
              setServerAudioMetrics(data);
              if (data.pipeline_status) {
                setPipelineStatus(data.pipeline_status);
              }
              return;
            }

            // Route standard telemetry analysis packets
            if (typeof data.risk_score === 'number' && data.metrics) {
              const packet: TelemetryPacket = data;
              setLatestPacket(packet);
              setPipelineStatus(data.pipeline_status || 'ANALYZING');
              setHistory((prev) => [...prev.slice(-49), packet]);
              onPacketReceived?.(packet);
            }
          } catch (err) {
            console.error('[V-SHIELD WS] Failed to parse JSON packet:', err);
          }
        }
      };

      ws.onerror = (err) => {
        console.warn('[V-SHIELD WS] Socket connection warning:', err);
        setStatus('error');
      };

      ws.onclose = () => {
        setStatus('disconnected');
      };

      wsRef.current = ws;
    } catch (err) {
      console.error('[V-SHIELD WS] Connection failed:', err);
      setStatus('error');
    }
  }, [url, speakerId, onPacketReceived]);

  const startSession = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'start', speaker_id: speakerId }));
    } else {
      connect();
    }
  }, [connect, speakerId]);

  const stopSession = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'stop' }));
    }
  }, []);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setStatus('disconnected');
  }, []);

  const sendAudioChunk = useCallback((pcmChunk: ArrayBuffer | Uint8Array) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(pcmChunk);
    }
  }, []);

  const switchSpeaker = useCallback((newSpeakerId: string) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'switch_speaker', speaker_id: newSpeakerId }));
    }
  }, []);

  const resetCall = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'reset' }));
    }
    setLatestPacket(null);
    setServerAudioMetrics(null);
    setHistory([]);
  }, []);

  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  return {
    status,
    pipelineStatus,
    latestPacket,
    serverAudioMetrics,
    history,
    lastError,
    connect,
    disconnect,
    startSession,
    stopSession,
    sendAudioChunk,
    switchSpeaker,
    resetCall,
    isConnected: status === 'connected',
  };
}
