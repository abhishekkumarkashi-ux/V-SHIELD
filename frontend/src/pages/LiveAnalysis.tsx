import { useState, useEffect, useRef, useCallback } from 'react';
import { PhoneOff, BarChart2, Activity, ShieldAlert, ShieldCheck, Play, AlertTriangle } from 'lucide-react';
import { AreaChart, Area, YAxis, ResponsiveContainer } from 'recharts';
import wsService from '../services/websocket';
import { AudioRecorder } from '../audio/AudioRecorder';

type AnalysisState = 
  | 'idle' 
  | 'requesting_permission' 
  | 'connecting' 
  | 'connected' 
  | 'analyzing' 
  | 'backend_error' 
  | 'authentication_error' 
  | 'microphone_error' 
  | 'model_unavailable' 
  | 'disconnected' 
  | 'stopping' 
  | 'stopped';

const INITIAL_WAVEFORM = Array.from({ length: 32 }, (_, i) => ({
  name: i,
  amplitude: 0,
}));

const LiveAnalysis = () => {
  const [analysisState, setAnalysisState] = useState<AnalysisState>('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [wsData, setWsData] = useState<any>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [waveformData, setWaveformData] = useState(INITIAL_WAVEFORM);
  const [elapsed, setElapsed] = useState(0);

  const recorderRef = useRef<AudioRecorder | null>(null);
  const animationFrameRef = useRef<number | null>(null);

  // Timer for active recording
  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | null = null;
    if (isRecording) {
      timer = setInterval(() => {
        setElapsed(prev => prev + 1);
      }, 1000);
    } else {
      setElapsed(0);
    }
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [isRecording]);

  // Real microphone audio visualizer via Web Audio API AnalyserNode
  const updateWaveform = useCallback(() => {
    const analyser = recorderRef.current?.getAnalyser();
    if (analyser && isRecording) {
      const dataArray = new Uint8Array(analyser.frequencyBinCount);
      analyser.getByteFrequencyData(dataArray);

      // Downsample to 32 points for chart rendering
      const step = Math.max(1, Math.floor(dataArray.length / 32));
      const points = Array.from({ length: 32 }, (_, i) => {
        const val = dataArray[i * step] || 0;
        return {
          name: i,
          amplitude: (val / 255) * 100, // Normalized 0 - 100%
        };
      });
      setWaveformData(points);
      animationFrameRef.current = requestAnimationFrame(updateWaveform);
    } else {
      setWaveformData(INITIAL_WAVEFORM);
    }
  }, [isRecording]);

  useEffect(() => {
    if (isRecording) {
      animationFrameRef.current = requestAnimationFrame(updateWaveform);
    } else {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      setWaveformData(INITIAL_WAVEFORM);
    }
    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [isRecording, updateWaveform]);

  const handleStart = async () => {
    setErrorMessage(null);
    setAnalysisState('requesting_permission');

    try {
      // 1. Initialize Audio Recorder with real microphone
      recorderRef.current = new AudioRecorder((chunk) => {
        wsService.sendAudioChunk(chunk);
      });

      await recorderRef.current.start();
      setAnalysisState('connecting');

      // 2. Connect WebSocket
      wsService.connect(
        (data) => {
          if (data.type === 'error') {
            setErrorMessage(data.message || 'Analysis error');
            if (data.message?.includes('Authentication')) {
              setAnalysisState('authentication_error');
            } else {
              setAnalysisState('backend_error');
            }
          } else if (data.type === 'analysis') {
            setWsData(data);
            setAnalysisState('analyzing');
          }
        },
        (statusData) => {
          if (statusData.type === 'error') {
            setErrorMessage('WebSocket network connection failed');
            setAnalysisState('backend_error');
          } else if (statusData.status === 'connected') {
            setAnalysisState('connected');
          } else if (statusData.status === 'disconnected') {
            setAnalysisState('disconnected');
            setIsRecording(false);
          } else if (statusData.status === 'stopped') {
            setAnalysisState('stopped');
            setIsRecording(false);
          }
        }
      );

      setIsRecording(true);
    } catch (err: any) {
      console.error('Microphone capture error:', err);
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        setErrorMessage('Microphone access denied by user. Please allow microphone permissions.');
        setAnalysisState('microphone_error');
      } else {
        setErrorMessage(err.message || 'Failed to initialize audio input device.');
        setAnalysisState('microphone_error');
      }
      handleStop();
    }
  };

  const handleStop = () => {
    setAnalysisState('stopping');
    if (recorderRef.current) {
      recorderRef.current.stop();
      recorderRef.current = null;
    }
    wsService.disconnect();
    setIsRecording(false);
    setWaveformData(INITIAL_WAVEFORM);
    setAnalysisState('stopped');
  };

  useEffect(() => {
    return () => {
      if (recorderRef.current) {
        recorderRef.current.stop();
      }
      wsService.disconnect();
    };
  }, []);

  const riskScore = wsData?.impersonation_risk_score !== undefined 
    ? Math.round(wsData.impersonation_risk_score) 
    : 0;
  const spoofProb = wsData?.spoof_probability !== undefined 
    ? Math.round(wsData.spoof_probability * 100) 
    : 0;
  const speakerSim = wsData?.speaker_similarity !== undefined && wsData?.speaker_similarity !== null
    ? Math.round(wsData.speaker_similarity * 100) 
    : null;
  const modelStatus = wsData?.model_status || 'UNTRAINED';
  const productionReady = wsData?.production_ready === true;
  
  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60).toString().padStart(2, '0');
    const s = (secs % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  return (
    <div className="flex flex-col w-full h-full gap-5">
      {/* Model Integrity & Development Only Disclaimer Banner */}
      {!productionReady && (
        <div className="flex items-center justify-between px-4 py-2.5 bg-amber-500/10 border border-amber-500/30 rounded-lg text-amber-300 text-xs font-medium">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
            <span>
              <strong>PHASE 1 NOTICE:</strong> Anti-spoof model status is <span className="font-mono bg-amber-500/20 px-1.5 py-0.5 rounded font-bold">{modelStatus}</span> (Development Checkpoint). Deepfake predictions are for pipeline verification only and not validated for production security.
            </span>
          </div>
          <span className="font-mono text-[11px] uppercase tracking-wider text-amber-400/80">DEV ONLY</span>
        </div>
      )}

      {/* Top Header Section */}
      <div className="flex flex-col gap-4 border-b border-outline-variant/50 pb-5">
        <div className="flex justify-between items-start">
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-3 mb-1">
              <h1 className="font-headline-xl text-3xl text-on-surface tracking-tight font-semibold">Live Voice Protection</h1>
              <div className={`flex items-center gap-2 px-3 py-1 border rounded font-code-sm text-xs font-bold tracking-widest uppercase ${
                isRecording 
                  ? 'bg-[#45e0a0]/10 border-[#45e0a0]/30 text-[#45e0a0]' 
                  : 'bg-surface-variant/50 border-outline-variant text-outline'
              }`}>
                {isRecording && <div className="w-2 h-2 rounded-full bg-[#45e0a0] animate-pulse" />}
                STATUS: {analysisState.toUpperCase()}
              </div>
            </div>
            <div className="flex items-center gap-6 font-label-sm text-[10px] text-outline uppercase tracking-wider">
              <span><span className="text-on-surface/50">SAMPLE RATE:</span> 16,000 HZ MONO</span>
              <span><span className="text-on-surface/50">WINDOWING:</span> 4.0S (1.0S HOP)</span>
              <span><span className="text-on-surface/50">MODEL STATUS:</span> {modelStatus}</span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {!isRecording ? (
              <button 
                onClick={handleStart} 
                className="flex items-center gap-2 px-4 py-2 bg-[#45e0a0]/10 border border-[#45e0a0]/50 text-[#45e0a0] hover:bg-[#45e0a0]/20 transition-colors rounded font-label-sm text-xs uppercase tracking-wider font-bold"
              >
                <Play className="w-4 h-4" /> Start Live Analysis
              </button>
            ) : (
              <button 
                onClick={handleStop} 
                className="flex items-center gap-2 px-4 py-2 border border-[#ffaaa0]/50 text-[#ffaaa0] bg-[#ffaaa0]/10 hover:bg-[#ffaaa0]/20 transition-colors rounded font-label-sm text-xs uppercase tracking-wider font-bold"
              >
                <PhoneOff className="w-4 h-4" /> Stop Analysis
              </button>
            )}
          </div>
        </div>

        {/* Error Alert Display */}
        {errorMessage && (
          <div className="flex items-center gap-2 px-4 py-2.5 bg-error/10 border border-error/30 rounded text-error text-xs">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* Real Stream Telemetry Grid */}
        <div className="grid grid-cols-6 gap-4">
          <div className="flex flex-col gap-1">
            <span className="font-label-sm text-[10px] text-outline uppercase tracking-widest">AUDIO INPUT</span>
            <span className="font-code-md text-[13px] text-on-surface">Microphone (Web Audio)</span>
          </div>
          <div className="flex flex-col gap-1">
            <span className="font-label-sm text-[10px] text-outline uppercase tracking-widest">ENCODING</span>
            <span className="font-code-md text-[13px] text-[#00c8e8]">Float32 PCM (16kHz)</span>
          </div>
          <div className="flex flex-col gap-1">
            <span className="font-label-sm text-[10px] text-outline uppercase tracking-widest">VAD STATE</span>
            <span className={`font-code-md text-[13px] font-bold ${wsData?.vad === 'SPEECH' ? 'text-[#45e0a0]' : 'text-outline'}`}>
              {wsData?.vad || (isRecording ? 'LISTENING' : 'IDLE')}
            </span>
          </div>
          <div className="flex flex-col gap-1">
            <span className="font-label-sm text-[10px] text-outline uppercase tracking-widest">ROUNDTRIP LATENCY</span>
            <span className="font-code-md text-[13px] text-[#45e0a0]">
              {wsData?.latency_ms !== undefined ? `${wsData.latency_ms}ms` : '0ms'}
            </span>
          </div>
          <div className="flex flex-col gap-1">
            <span className="font-label-sm text-[10px] text-outline uppercase tracking-widest">SESSION ELAPSED</span>
            <span className="font-code-md text-[13px] text-on-surface flex items-center gap-2">
              <div className={`w-1.5 h-1.5 rounded-full ${isRecording ? 'bg-[#00c8e8] animate-pulse' : 'bg-outline'}`} />
              {formatTime(elapsed)}
            </span>
          </div>
          <div className="flex flex-col gap-1">
            <span className="font-label-sm text-[10px] text-outline uppercase tracking-widest">BUFFER LEVEL</span>
            <span className="font-code-md text-[13px] text-[#00c8e8]">
              {wsData?.buffer_duration_ms ? `${wsData.buffer_duration_ms}ms / 4000ms` : (isRecording ? 'Active' : '0ms')}
            </span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        {/* Left Column: Real Audio Waveform & DSP Status */}
        <div className="xl:col-span-2 flex flex-col gap-5">
          <div className="bg-[#0f172a] rounded-lg border border-outline-variant p-6 flex flex-col gap-4 shadow-lg">
            <div className="flex justify-between items-start">
              <div className="flex items-center gap-3">
                <BarChart2 className="w-5 h-5 text-[#00c8e8]" />
                <h3 className="font-headline-sm text-lg text-on-surface font-semibold tracking-tight">Real-Time Acoustic Spectrum</h3>
              </div>
              <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${isRecording ? 'bg-[#00c8e8] animate-pulse' : 'bg-outline'}`} />
                <span className="font-label-sm text-[10px] text-on-surface uppercase tracking-wider">
                  {isRecording ? 'Live Microphone Input (Web Audio Analyser)' : 'Microphone Inactive'}
                </span>
              </div>
            </div>

            <div className="flex items-center gap-6 font-code-sm text-[10px] text-outline uppercase tracking-widest mb-2 border-b border-outline-variant/30 pb-2">
              <span>AUDIO BUFFER: <span className="text-[#00c8e8] font-bold">{wsData?.buffer_samples || 0} samples</span></span>
              <span>INFERENCE TIME: <span className="text-[#45e0a0] font-bold">{wsData?.inference_ms || 0}ms</span></span>
              <span>ENERGY RMS: <span className="text-on-surface font-bold">{wsData?.rms ? wsData.rms.toFixed(4) : '0.0000'}</span></span>
            </div>
            
            <div className="h-64 w-full relative">
              {isRecording ? (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={waveformData}>
                    <defs>
                      <linearGradient id="colorWave" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#00c8e8" stopOpacity={0.4}/>
                        <stop offset="95%" stopColor="#00c8e8" stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <YAxis hide domain={[0, 100]} />
                    <Area 
                      type="monotone" 
                      dataKey="amplitude" 
                      stroke="#00c8e8" 
                      strokeWidth={2}
                      fill="url(#colorWave)" 
                      isAnimationActive={false}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex flex-col items-center justify-center h-full text-outline/60 text-xs">
                  <Activity className="w-8 h-8 mb-2 stroke-1" />
                  <span>Microphone is in standby. Click "Start Live Analysis" to begin real-time streaming.</span>
                </div>
              )}
            </div>
            
            {/* Real Pipeline Stages */}
            <div className="grid grid-cols-4 gap-4 mt-2 pt-3 border-t border-outline-variant/30">
              <div className="flex flex-col gap-1">
                <span className="font-label-sm text-[9px] text-outline uppercase tracking-wider">Acoustic Input</span>
                <span className="font-code-md text-xs text-[#00c8e8] font-bold">16,000 Hz Float32</span>
                <span className="font-label-sm text-[10px] text-on-surface">({isRecording ? 'Streaming' : 'Standby'})</span>
              </div>
              <div className="flex flex-col gap-1">
                <span className="font-label-sm text-[9px] text-outline uppercase tracking-wider">Voice Activity (VAD)</span>
                <span className="font-code-md text-xs text-[#45e0a0] font-bold">Energy Threshold</span>
                <span className="font-label-sm text-[10px] text-[#45e0a0]">{wsData?.vad || 'IDLE'}</span>
              </div>
              <div className="flex flex-col gap-1">
                <span className="font-label-sm text-[9px] text-outline uppercase tracking-wider">Anti-Spoofing</span>
                <span className="font-code-md text-xs text-amber-400 font-bold">{modelStatus}</span>
                <span className="font-label-sm text-[10px] text-outline">(Checkpoint v1)</span>
              </div>
              <div className="flex flex-col gap-1">
                <span className="font-label-sm text-[9px] text-outline uppercase tracking-wider">Speaker Status</span>
                <span className="font-code-md text-xs text-[#00c8e8] font-bold">{wsData?.speaker_status || 'NOT_ENROLLED'}</span>
                <span className="font-label-sm text-[10px] text-on-surface">ECAPA-TDNN</span>
              </div>
            </div>
          </div>
          
          {/* Active Pipeline Status */}
          <div className="bg-[#0f172a] rounded-lg border border-outline-variant p-5 shadow-lg flex flex-col gap-4">
             <div className="flex justify-between items-center">
               <h3 className="font-headline-sm text-sm text-on-surface font-semibold flex items-center gap-2">
                 <Activity className="w-4 h-4 text-[#00c8e8]" />
                 Pipeline Execution State
               </h3>
               <span className="font-code-sm text-[10px] text-[#45e0a0] uppercase tracking-widest font-bold">
                 {isRecording ? 'STREAMING ACTIVE' : 'SYSTEM STANDBY'}
               </span>
             </div>
             <div className="flex items-center justify-between mt-2 px-2 relative">
               <div className="absolute top-1 left-4 right-4 h-[1px] bg-outline-variant z-0" />
               {[
                 { step: '01', title: 'Microphone', desc: isRecording ? 'Active' : 'Standby' },
                 { step: '02', title: 'Worklet PCM', desc: '16kHz Mono' },
                 { step: '03', title: 'VAD Filter', desc: wsData?.vad || 'Standby' },
                 { step: '04', title: 'Buffer (4s)', desc: `${wsData?.buffer_duration_ms || 0}ms` },
                 { step: '05', title: 'Anti-Spoof', desc: modelStatus },
                 { step: '06', title: 'Speaker Verif', desc: wsData?.speaker_status || 'Standby' },
                 { step: '07', title: 'Risk Engine', desc: wsData?.impersonation_risk_level || 'Standby' },
               ].map((node, i) => (
                 <div key={i} className="flex flex-col gap-1 z-10 bg-[#0f172a] px-2 relative">
                   <div className={`w-2 h-2 rounded-full mb-1 transition-transform ${isRecording ? 'bg-[#45e0a0]' : 'bg-outline'}`} />
                   <span className="font-label-sm text-[9px] text-outline">{node.step}</span>
                   <span className="font-label-sm text-[11px] text-on-surface font-bold whitespace-nowrap">{node.title}</span>
                   <span className="font-label-sm text-[9px] text-[#00c8e8]">{node.desc}</span>
                 </div>
               ))}
             </div>
          </div>
        </div>

        {/* Right Column: Risk Assessment & Diagnostics */}
        <div className="xl:col-span-1 flex flex-col gap-5">
          <div className="bg-[#0f172a] rounded-lg border border-outline-variant p-6 flex flex-col gap-6 shadow-lg">
            <h3 className="font-label-sm text-[10px] text-outline uppercase tracking-widest border-b border-outline-variant/50 pb-2">RISK ASSESSMENT</h3>
            
            <div className="flex flex-col items-center justify-center pt-2 pb-4">
              <div className="relative w-48 h-48 flex items-center justify-center">
                <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
                  <circle cx="50" cy="50" r="42" fill="transparent" stroke="#1e293b" strokeWidth="12" />
                  <circle 
                    cx="50" cy="50" r="42" 
                    fill="transparent" 
                    stroke={riskScore > 75 ? "#ffaaa0" : riskScore > 50 ? "#facc15" : "#45e0a0"} 
                    strokeWidth="12" 
                    strokeDasharray="263.89" 
                    strokeDashoffset={263.89 - (263.89 * riskScore) / 100} 
                    strokeLinecap="round" 
                  />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <div className="flex items-baseline gap-1 mt-2">
                    <span className="text-5xl font-headline-xl font-bold text-on-surface tracking-tighter">
                      {isRecording ? riskScore : '--'}
                    </span>
                    <span className="font-label-sm text-[10px] text-outline font-bold">/ 100</span>
                  </div>
                  <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest mt-1 font-bold">
                    IMPERSONATION RISK
                  </span>
                </div>
              </div>
              
              <div className={`mt-8 px-4 py-2 border rounded flex items-center gap-2 ${
                !isRecording ? 'bg-surface-variant/30 border-outline-variant text-outline' :
                riskScore > 75 ? 'bg-error/10 border-error/30 text-error' : 
                riskScore > 50 ? 'bg-yellow-500/10 border-yellow-500/30 text-yellow-500' : 
                'bg-[#45e0a0]/10 border-[#45e0a0]/30 text-[#45e0a0]'
              }`}>
                {riskScore > 75 ? <ShieldAlert className="w-4 h-4" /> : <ShieldCheck className="w-4 h-4" />}
                <span className="font-label-sm text-[10px] font-bold tracking-widest uppercase">
                  {!isRecording ? 'STANDBY' :
                   riskScore > 75 ? 'HIGH RISK' : 
                   riskScore > 50 ? 'MEDIUM RISK' : 
                   'LOW RISK'}
                </span>
              </div>
            </div>
            
            <div className="border-t border-outline-variant/50 pt-6 flex flex-col gap-5">
              <div className="flex justify-between items-center mb-1">
                <h3 className="font-headline-sm text-sm text-on-surface font-semibold">Biometric Telemetry</h3>
                <span className="font-label-sm text-[9px] text-outline uppercase tracking-wider font-bold">Live Feed</span>
              </div>
              
              <div className="flex flex-col gap-1.5">
                <div className="flex justify-between items-center font-label-sm text-[11px]">
                  <span className="text-outline">Anti-Spoof Raw Probability</span>
                  <span className="text-amber-400 font-bold">{isRecording ? `${spoofProb}%` : '--'}</span>
                </div>
                <div className="h-1.5 w-full bg-surface-container-highest rounded overflow-hidden">
                  <div className="h-full bg-amber-400 transition-all duration-300" style={{ width: `${isRecording ? spoofProb : 0}%` }}></div>
                </div>
              </div>
              
              <div className="flex flex-col gap-1.5">
                <div className="flex justify-between items-center font-label-sm text-[11px]">
                  <span className="text-outline">Speaker Profile Match</span>
                  <span className="text-[#00c8e8] font-bold">{speakerSim !== null ? `${speakerSim}%` : 'Not Enrolled'}</span>
                </div>
                <div className="h-1.5 w-full bg-surface-container-highest rounded overflow-hidden">
                  <div className="h-full bg-[#00c8e8] transition-all duration-300" style={{ width: `${speakerSim !== null ? speakerSim : 0}%` }}></div>
                </div>
              </div>

              {wsData?.risk_reasons && wsData.risk_reasons.length > 0 && (
                <div className="flex flex-col gap-1 pt-2 border-t border-outline-variant/30">
                  <span className="font-label-sm text-[10px] text-outline uppercase tracking-widest">Risk Factors:</span>
                  <ul className="list-disc list-inside text-xs text-amber-300">
                    {wsData.risk_reasons.map((r: string, idx: number) => (
                      <li key={idx}>{r}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LiveAnalysis;
