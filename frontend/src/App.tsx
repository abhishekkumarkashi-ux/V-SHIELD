import React, { useState, useEffect } from 'react';
import {
  Shield,
  Mic,
  MicOff,
  PhoneCall,
  UserCheck,
  Square,
  Sparkles,
  Wifi,
  WifiOff,
  UploadCloud,
  AlertTriangle,
} from 'lucide-react';

import { useVShieldSocket } from './hooks/useVShieldSocket';
import { useAudioStreamer } from './hooks/useAudioStreamer';
import { RiskGauge } from './components/RiskGauge';
import { AudioWaveform } from './components/AudioWaveform';
import { TelemetryBreakdown } from './components/TelemetryBreakdown';
import { MitigationAlert } from './components/MitigationAlert';
import { FileUploadAnalyzer } from './components/FileUploadAnalyzer';
import { fetchHealth, fetchSpeakers, ensureAuthToken, SystemHealth } from './services/api';

interface SpeakerOption {
  speaker_id: string;
  name: string;
}

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'live' | 'upload'>('live');
  const [selectedSpeaker, setSelectedSpeaker] = useState<string>('exec-001');
  const [speakersList, setSpeakersList] = useState<SpeakerOption[]>([
    { speaker_id: 'exec-001', name: 'Dr. Rajesh Sharma (CTO)' },
    { speaker_id: 'exec-002', name: 'Ananya Iyer (VP Finance)' },
    { speaker_id: 'exec-003', name: 'Vikram Malhotra (Treasury Controller)' },
  ]);
  const [alertMessage, setAlertMessage] = useState<string | null>(null);
  const [backendHealth, setBackendHealth] = useState<SystemHealth | null>(null);
  const [backendStatus, setBackendStatus] = useState<
    'CHECKING' | 'ONLINE' | 'MODEL_ERROR' | 'DEGRADED' | 'OFFLINE'
  >('CHECKING');

  // WebSocket Telemetry Hook
  const {
    latestPacket,
    serverAudioMetrics,
    pipelineStatus,
    history,
    lastError,
    connect: connectWs,
    disconnect: disconnectWs,
    startSession,
    stopSession,
    sendAudioChunk,
    switchSpeaker,
    resetCall,
    isConnected,
    activeCallSid,
    activeCallerPhone,
    activeCallStatus,
  } = useVShieldSocket({
    speakerId: selectedSpeaker,
  });

  // Authenticate operator session and connect telemetry websocket on mount
  useEffect(() => {
    ensureAuthToken();
    connectWs();
  }, [connectWs]);

  useEffect(() => {
    if (lastError) {
      setAlertMessage(`Gateway Notice: ${lastError}`);
      const timer = setTimeout(() => setAlertMessage(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [lastError]);

  // Microphone / Audio Streamer Hook
  const {
    isStreaming,
    isMuted,
    rmsVolume,
    debugInfo,
    startStreaming,
    stopStreaming,
    toggleMute,
    startSimulation,
    analyser,
  } = useAudioStreamer({
    onAudioChunk: sendAudioChunk,
  });

  // Health Polling & Speaker Loading
  useEffect(() => {
    let isMounted = true;

    const checkHealth = async () => {
      try {
        const health = await fetchHealth();
        if (!isMounted) return;
        setBackendHealth(health);
        if (health.model_loaded && (health.status === 'ok' || health.status === 'ONLINE')) {
          setBackendStatus('ONLINE');
        } else if (!health.model_loaded) {
          setBackendStatus('MODEL_ERROR');
        } else if (health.status === 'degraded') {
          setBackendStatus('DEGRADED');
        } else {
          setBackendStatus('ONLINE');
        }
      } catch {
        if (!isMounted) return;
        setBackendHealth(null);
        setBackendStatus('OFFLINE');
      }
    };

    // Initial check and 5s polling
    checkHealth();
    const interval = setInterval(checkHealth, 5000);

    // Fetch registered speakers from backend
    fetchSpeakers()
      .then((data) => {
        if (isMounted && Array.isArray(data) && data.length > 0) {
          setSpeakersList(
            data.map((s) => ({
              speaker_id: s.speaker_id,
              name: s.name || s.speaker_id,
            }))
          );
        }
      })
      .catch(() => {
        // Fallback default profiles
      });

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  const handleStartCall = async () => {
    connectWs();
    startSession();
    try {
      await startStreaming();
    } catch {
      // If mic fails, trigger simulated genuine stream
      startSimulation('genuine');
    }
  };

  const handleStopCall = () => {
    stopStreaming();
    stopSession();
    disconnectWs();
    resetCall();
  };

  const handleSpeakerChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value;
    setSelectedSpeaker(val);
    switchSpeaker(val);
  };

  // Mock action triggers
  const handleTriggerMfa = () => {
    setAlertMessage('Out-of-band MFA push notification sent to authorized executive device.');
    setTimeout(() => setAlertMessage(null), 5000);
  };

  const handleTerminate = () => {
    handleStopCall();
    setAlertMessage('Call quarantined and disconnected. Security incident logged.');
    setTimeout(() => setAlertMessage(null), 5000);
  };

  const isCallActive = isStreaming || activeCallStatus === 'STREAMING';
  const currentRiskScore = latestPacket?.risk_score ?? null;
  const currentClassification =
    latestPacket?.classification ??
    (isCallActive ? (pipelineStatus === 'ANALYZING' ? 'ANALYZING' : 'LISTENING') : 'WAITING');
  const currentAction = latestPacket?.recommended_action ?? null;

  const currentSpeakerObj = speakersList.find((s) => s.speaker_id === selectedSpeaker);

  return (
    <div className="min-h-screen bg-[#070b14] text-slate-100 flex flex-col">
      {/* Top Navigation Bar */}
      <header className="border-b border-slate-800/80 bg-[#0d1322]/80 backdrop-blur-md px-6 py-3.5 sticky top-0 z-50 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-gradient-to-tr from-cyan-600 to-blue-600 rounded-xl shadow-lg shadow-cyan-900/30">
            <Shield className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-base font-extrabold tracking-tight text-white">V-SHIELD</h1>
              <span className="text-[10px] font-mono font-bold bg-cyan-950 text-cyan-400 border border-cyan-500/30 px-1.5 py-0.5 rounded">
                SIH 2026 #26104
              </span>
            </div>
            <p className="text-[11px] text-slate-400">Real-Time Voice Impersonation Defense & Fraud Prevention</p>
          </div>
        </div>

        {/* System Telemetry & Status Badges */}
        <div className="flex items-center space-x-4">
          <div className="hidden sm:flex items-center space-x-2 text-xs font-mono bg-slate-900/80 border border-slate-800 px-3 py-1.5 rounded-lg">
            {backendStatus === 'ONLINE' ? (
              <>
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                <span className="text-slate-300">{backendHealth?.anti_spoof_model || 'AASIST (Graph Attn)'}</span>
                <span className="text-slate-600">|</span>
                <span className="text-slate-300">ECAPA-TDNN ({backendHealth?.device?.toUpperCase() || 'CPU'})</span>
              </>
            ) : backendStatus === 'MODEL_ERROR' ? (
              <>
                <span className="w-2 h-2 rounded-full bg-red-500"></span>
                <span className="text-red-400 font-semibold">MODEL LOAD ERROR</span>
              </>
            ) : backendStatus === 'DEGRADED' ? (
              <>
                <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse"></span>
                <span className="text-amber-300 font-semibold">DEGRADED (PARTIAL AI)</span>
              </>
            ) : backendStatus === 'CHECKING' ? (
              <>
                <span className="w-2 h-2 rounded-full bg-slate-400 animate-ping"></span>
                <span className="text-slate-400">CONNECTING...</span>
              </>
            ) : (
              <>
                <span className="w-2 h-2 rounded-full bg-slate-600"></span>
                <span className="text-slate-500">BACKEND OFFLINE</span>
              </>
            )}
          </div>

          {/* Twilio Active PSTN Telephony Call Badge */}
          {activeCallSid && (
            <div className="flex items-center space-x-2 text-xs font-mono bg-purple-950/80 border border-purple-500/60 text-purple-300 px-3 py-1.5 rounded-lg shadow-lg animate-pulse">
              <PhoneCall className="w-3.5 h-3.5 text-purple-400" />
              <span className="font-bold text-white">TWILIO:</span>
              <span className="text-purple-200">{activeCallSid.slice(0, 12)}...</span>
              {activeCallerPhone && <span className="text-purple-400">({activeCallerPhone})</span>}
            </div>
          )}

          <div
            className={`flex items-center space-x-1.5 text-xs font-mono px-3 py-1.5 rounded-lg border transition-colors ${
              backendStatus === 'ONLINE'
                ? 'bg-emerald-950/60 border-emerald-500/40 text-emerald-400'
                : backendStatus === 'MODEL_ERROR'
                ? 'bg-red-950/60 border-red-500/40 text-red-400'
                : backendStatus === 'DEGRADED'
                ? 'bg-amber-950/60 border-amber-500/40 text-amber-300'
                : backendStatus === 'CHECKING'
                ? 'bg-slate-900 border-slate-700 text-slate-400'
                : 'bg-slate-900 border-slate-800 text-slate-500'
            }`}
          >
            {backendStatus === 'ONLINE' ? (
              <>
                <Wifi className="w-3.5 h-3.5 text-emerald-400" />
                <span className="font-semibold">ONLINE</span>
                {isConnected && (
                  <>
                    <span className="text-emerald-600 font-bold">•</span>
                    <span className="text-cyan-400 font-semibold text-[10px]">
                      {activeCallSid ? 'TELEPHONY STREAM' : 'GATEWAY CONNECTED'}
                    </span>
                  </>
                )}
              </>
            ) : backendStatus === 'MODEL_ERROR' ? (
              <>
                <AlertTriangle className="w-3.5 h-3.5 text-red-400" />
                <span className="font-semibold">MODEL ERROR</span>
              </>
            ) : backendStatus === 'DEGRADED' ? (
              <>
                <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                <span className="font-semibold">DEGRADED</span>
              </>
            ) : backendStatus === 'CHECKING' ? (
              <>
                <span className="w-2 h-2 rounded-full bg-slate-400 animate-ping mr-1"></span>
                <span className="font-medium">CHECKING...</span>
              </>
            ) : (
              <>
                <WifiOff className="w-3.5 h-3.5 text-slate-500" />
                <span>OFFLINE</span>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Action Notification Toast */}
      {alertMessage && (
        <div className="bg-cyan-950/90 border border-cyan-500/50 text-cyan-200 px-6 py-2.5 text-center text-xs font-semibold shadow-lg shadow-cyan-950/50 flex items-center justify-center space-x-2">
          <Sparkles className="w-4 h-4 text-cyan-400 animate-spin" />
          <span>{alertMessage}</span>
        </div>
      )}

      {/* Main Operations Dashboard */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 md:p-6 space-y-5">
        {/* Operations Mode Switcher */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-2">
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setActiveTab('live')}
              className={`px-4 py-2 rounded-xl text-xs font-bold flex items-center space-x-2 transition ${
                activeTab === 'live'
                  ? 'bg-cyan-950 border border-cyan-500/50 text-cyan-300 shadow-lg shadow-cyan-950/50'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/50'
              }`}
            >
              <PhoneCall className="w-3.5 h-3.5" />
              <span>Live Call Ingestion (WebSocket)</span>
            </button>
            <button
              onClick={() => setActiveTab('upload')}
              className={`px-4 py-2 rounded-xl text-xs font-bold flex items-center space-x-2 transition ${
                activeTab === 'upload'
                  ? 'bg-cyan-950 border border-cyan-500/50 text-cyan-300 shadow-lg shadow-cyan-950/50'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/50'
              }`}
            >
              <UploadCloud className="w-3.5 h-3.5" />
              <span>Audio File Upload Analysis (REST API)</span>
            </button>
          </div>
          <span className="hidden sm:inline-block text-[11px] font-mono text-slate-500">
            {activeTab === 'live' ? 'Protocol: ws://localhost:8000/ws/live-call' : 'Endpoint: POST /api/v1/analyze-file'}
          </span>
        </div>

        {activeTab === 'upload' ? (
          <FileUploadAnalyzer />
        ) : (
          <>
            {/* Call Ingestion & Session Control Header */}
            <div className="glass-panel p-4 rounded-2xl flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-3">
            {/* Caller Profile Selection */}
            <div className="flex items-center space-x-2 bg-slate-900/90 border border-slate-800 rounded-xl px-3 py-2">
              <UserCheck className="w-4 h-4 text-purple-400" />
              <label className="text-xs font-medium text-slate-400">Target Voiceprint:</label>
              <select
                value={selectedSpeaker}
                onChange={handleSpeakerChange}
                className="bg-transparent text-xs font-semibold text-slate-200 focus:outline-none cursor-pointer"
              >
                {speakersList.map((spk) => (
                  <option key={spk.speaker_id} value={spk.speaker_id} className="bg-slate-900 text-slate-100">
                    {spk.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Ingestion Stream Toggle */}
            {!isStreaming ? (
              <button
                onClick={handleStartCall}
                className="px-4 py-2 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-bold text-xs rounded-xl flex items-center space-x-2 shadow-lg shadow-cyan-900/30 transition"
              >
                <PhoneCall className="w-4 h-4" />
                <span>Start Live Call Stream</span>
              </button>
            ) : (
              <div className="flex items-center space-x-2">
                <button
                  onClick={toggleMute}
                  className={`px-3 py-2 rounded-xl text-xs font-semibold flex items-center space-x-1.5 border transition ${
                    isMuted
                      ? 'bg-amber-950 border-amber-500 text-amber-300'
                      : 'bg-slate-800 border-slate-700 text-slate-200'
                  }`}
                >
                  {isMuted ? <MicOff className="w-3.5 h-3.5" /> : <Mic className="w-3.5 h-3.5" />}
                  <span>{isMuted ? 'Unmute' : 'Mute'}</span>
                </button>
                <button
                  onClick={handleStopCall}
                  className="px-4 py-2 bg-red-600 hover:bg-red-500 text-white font-bold text-xs rounded-xl flex items-center space-x-1.5 shadow-lg shadow-red-900/30 transition"
                >
                  <Square className="w-3.5 h-3.5 fill-current" />
                  <span>End Call</span>
                </button>
              </div>
            )}

            {/* Live Audio Ingestion Diagnostics */}
            {isStreaming && (
              <div className="hidden lg:flex items-center space-x-2 text-[10px] font-mono text-cyan-400/90 bg-cyan-950/40 border border-cyan-800/40 rounded-xl px-3 py-1.5 shadow-inner">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                <span className="font-semibold text-slate-200">
                  {serverAudioMetrics ? `${serverAudioMetrics.sample_rate / 1000}kHz Stream` : '16kHz Audio'}
                </span>
                <span className="text-slate-600">|</span>
                <span>
                  {serverAudioMetrics
                    ? `RMS: ${serverAudioMetrics.rms.toFixed(4)}`
                    : rmsVolume > 0
                    ? `Mic: ${rmsVolume.toFixed(3)}`
                    : debugInfo
                    ? `${debugInfo.chunkDurationMs}ms chunks`
                    : 'Ingesting'}
                </span>
                <span className="text-slate-600">|</span>
                <span>
                  {serverAudioMetrics?.speech_state
                    ? `VAD: ${serverAudioMetrics.speech_state}`
                    : `State: ${pipelineStatus}`}
                </span>
                {serverAudioMetrics && (
                  <>
                    <span className="text-slate-600">|</span>
                    <span>Peak: {serverAudioMetrics.peak.toFixed(3)}</span>
                  </>
                )}
              </div>
            )}
          </div>

          {/* Quick Simulation Bench for Live Demonstrations */}
          <div className="flex items-center space-x-2 bg-slate-950/80 border border-slate-800/80 p-1.5 rounded-xl self-end md:self-auto">
            <span className="text-[11px] font-semibold text-slate-400 px-2 flex items-center space-x-1">
              <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
              <span>Simulate:</span>
            </span>
            <button
              onClick={() => {
                connectWs();
                startSimulation('genuine');
              }}
              className="px-2.5 py-1 text-[11px] font-medium bg-emerald-950/60 hover:bg-emerald-900/80 text-emerald-300 border border-emerald-500/30 rounded-lg transition"
            >
              Genuine Caller
            </button>
            <button
              onClick={() => {
                connectWs();
                startSimulation('clone');
              }}
              className="px-2.5 py-1 text-[11px] font-medium bg-red-950/60 hover:bg-red-900/80 text-red-300 border border-red-500/30 rounded-lg transition"
            >
              Voice Clone
            </button>
            <button
              onClick={() => {
                connectWs();
                startSimulation('unknown');
              }}
              className="px-2.5 py-1 text-[11px] font-medium bg-amber-950/60 hover:bg-amber-900/80 text-amber-300 border border-amber-500/30 rounded-lg transition"
            >
              Unknown Identity
            </button>
          </div>
        </div>

        {/* Dynamic Threat & Mitigation Banner */}
        <MitigationAlert
          action={currentAction}
          riskScore={currentRiskScore}
          isStreaming={isStreaming}
          onTriggerMfa={handleTriggerMfa}
          onTerminateCall={handleTerminate}
          onOverride={() => resetCall()}
        />

        {/* Core Multi-Signal Telemetry Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          {/* Left Column: Visual Risk Gauge & Waveform */}
          <div className="lg:col-span-5 flex flex-col space-y-5">
            <div className="glass-panel p-5 rounded-2xl flex flex-col items-center justify-between border-slate-800/80">
              <div className="w-full flex items-center justify-between text-xs text-slate-400 border-b border-slate-800 pb-3 mb-2">
                <span className="font-bold uppercase tracking-wider text-slate-300">
                  Dynamic Impersonation Risk
                </span>
                <span className="font-mono text-[11px] text-cyan-400">EMA (α = 0.70)</span>
              </div>

              <RiskGauge
                score={currentRiskScore}
                classification={currentClassification}
                isStreaming={isCallActive}
              />
            </div>

            {/* Audio Waveform with 300ms margin preservation guard */}
            <AudioWaveform
              analyser={analyser}
              isStreaming={isCallActive}
              rmsVolume={rmsVolume}
            />
          </div>

          {/* Right Column: Multi-Worker Telemetry Breakdown & Rolling Activity */}
          <div className="lg:col-span-7 flex flex-col space-y-5">
            {/* Multi-Signal Breakdown (AASIST + ECAPA + RMS + Latency) */}
            <div className="glass-panel p-5 rounded-2xl border-slate-800/80 space-y-3">
              <div className="flex items-center justify-between text-xs text-slate-400 border-b border-slate-800 pb-3">
                <span className="font-bold uppercase tracking-wider text-slate-300">
                  Parallel AI Analysis Engine
                </span>
                <span className="font-mono text-[11px] text-slate-500">
                  Sliding Window: 64,600 samples (Hop: 8,000)
                </span>
              </div>

              <TelemetryBreakdown
                metrics={latestPacket?.metrics ?? null}
                serverAudioMetrics={serverAudioMetrics}
                pipelineStatus={pipelineStatus}
                isStreaming={isCallActive}
                enrolledSpeakerName={currentSpeakerObj?.name}
              />
            </div>

            {/* Rolling Historical Risk Timeline */}
            <div className="glass-panel p-5 rounded-2xl border-slate-800/80 flex-1 flex flex-col justify-between">
              <div className="flex items-center justify-between text-xs text-slate-400 border-b border-slate-800 pb-3 mb-3">
                <span className="font-bold uppercase tracking-wider text-slate-300">
                  Rolling Call Threat Activity
                </span>
                <span className="font-mono text-[11px] text-slate-500">
                  Last {history.length} Sliding Windows (500ms intervals)
                </span>
              </div>

              <div className="h-32 w-full flex items-end space-x-1 bg-[#070b14]/80 p-2.5 rounded-xl border border-slate-800/60 overflow-hidden">
                {history.length === 0 ? (
                  <div className="w-full h-full flex items-center justify-center text-xs text-slate-500 font-mono">
                    Awaiting audio stream packets to populate time-series timeline...
                  </div>
                ) : (
                  history.map((pkt, idx) => {
                    const h = Math.max(6, Math.min(100, pkt.risk_score));
                    const isHigh = pkt.risk_score >= 70;
                    const isMed = pkt.risk_score >= 31 && pkt.risk_score < 70;
                    const barColor = isHigh
                      ? 'bg-red-500 shadow-sm shadow-red-500'
                      : isMed
                      ? 'bg-amber-500'
                      : 'bg-emerald-500';

                    return (
                      <div
                        key={idx}
                        className="flex-1 flex flex-col items-center justify-end h-full group relative"
                      >
                        <div
                          className={`w-full rounded-t-sm transition-all duration-200 ${barColor}`}
                          style={{ height: `${h}%` }}
                        />
                        {/* Tooltip on hover */}
                        <div className="hidden group-hover:block absolute -top-8 bg-slate-900 border border-slate-700 text-[10px] font-mono px-2 py-0.5 rounded text-white z-20 whitespace-nowrap pointer-events-none">
                          Risk: {pkt.risk_score.toFixed(1)}
                        </div>
                      </div>
                    );
                  })
                )}
              </div>

              <div className="flex items-center justify-between text-[11px] font-mono text-slate-500 mt-2 px-1">
                <span className="flex items-center space-x-1">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block"></span>
                  <span>Low &lt;30</span>
                </span>
                <span className="flex items-center space-x-1">
                  <span className="w-2 h-2 rounded-full bg-amber-500 inline-block"></span>
                  <span>Suspicious 31-69</span>
                </span>
                <span className="flex items-center space-x-1">
                  <span className="w-2 h-2 rounded-full bg-red-500 inline-block"></span>
                  <span>Voice Clone &gt;70</span>
                </span>
              </div>
            </div>
          </div>
        </div>
        </>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/60 bg-[#070b14] px-6 py-3 text-center text-xs text-slate-500 font-mono">
        V-SHIELD • Smart India Hackathon 2026 • Problem Statement ID: 26104 • Defense In Depth
      </footer>
    </div>
  );
};

export default App;
