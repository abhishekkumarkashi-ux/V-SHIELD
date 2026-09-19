import { useState, useEffect, useRef, useCallback } from 'react';

export interface TelemetryMetrics {
  spoof_probability: number;
  speaker_similarity: number;
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
}

export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error';

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
  const [latestPacket, setLatestPacket] = useState<TelemetryPacket | null>(null);
  const [history, setHistory] = useState<TelemetryPacket[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);

  const connect = useCallback(() => {
    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
      return;
    }

    setStatus('connecting');
    const wsUrl = new URL(url);
    if (speakerId) {
      wsUrl.searchParams.set('speaker_id', speakerId);
    }

    try {
      const ws = new WebSocket(wsUrl.toString());
      ws.binaryType = 'arraybuffer';

      ws.onopen = () => {
        setStatus('connected');
        console.log('[V-SHIELD WS] Connected to backend telemetry gateway');
      };

      ws.onmessage = (event) => {
        if (typeof event.data === 'string') {
          try {
            const packet: TelemetryPacket = JSON.parse(event.data);
            setLatestPacket(packet);
            setHistory((prev) => [...prev.slice(-49), packet]);
            onPacketReceived?.(packet);
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
      wsRef.current.send(JSON.stringify({ speaker_id: newSpeakerId }));
    }
  }, []);

  const resetCall = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: 'reset' }));
    }
    setLatestPacket(null);
    setHistory([]);
  }, []);

  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  return {
    status,
    latestPacket,
    history,
    connect,
    disconnect,
    sendAudioChunk,
    switchSpeaker,
    resetCall,
    isConnected: status === 'connected',
  };
}
