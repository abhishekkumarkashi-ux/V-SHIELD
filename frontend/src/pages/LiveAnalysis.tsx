import { useState, useEffect, useRef } from 'react';
import { Mic, MicOff, AlertCircle, Activity } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import { api } from '../services/api';

const LiveAnalysis = () => {
  const [isRecording, setIsRecording] = useState(false);
  const [wsStatus, setWsStatus] = useState<'connecting' | 'connected' | 'disconnected'>('disconnected');
  const [vadStatus, setVadStatus] = useState('SILENCE');
  const [latestAnalysis, setLatestAnalysis] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);
  
  const wsRef = useRef<WebSocket | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationRef = useRef<number>();

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current.stream.getTracks().forEach(track => track.stop());
    }
    if (wsRef.current) {
      wsRef.current.close();
    }
    if (animationRef.current) {
      cancelAnimationFrame(animationRef.current);
    }
    if (audioContextRef.current) {
      audioContextRef.current.close();
    }
    setIsRecording(false);
    setVadStatus('SILENCE');
  };

  useEffect(() => {
    return () => {
      stopRecording();
    };
  }, []);

  const drawWaveform = () => {
    if (!analyserRef.current || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const analyser = analyserRef.current;
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    
    const draw = () => {
      animationRef.current = requestAnimationFrame(draw);
      analyser.getByteTimeDomainData(dataArray);

      ctx.fillStyle = 'rgb(2, 6, 23)'; // slate-950
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      ctx.lineWidth = 2;
      ctx.strokeStyle = vadStatus === 'SPEECH' ? 'rgb(59, 130, 246)' : 'rgb(51, 65, 85)'; // blue-500 or slate-700
      ctx.beginPath();

      const sliceWidth = canvas.width * 1.0 / bufferLength;
      let x = 0;

      for (let i = 0; i < bufferLength; i++) {
        const v = dataArray[i] / 128.0;
        const y = v * canvas.height / 2;

        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
        x += sliceWidth;
      }
      ctx.lineTo(canvas.width, canvas.height / 2);
      ctx.stroke();
    };
    draw();
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      // Setup Analyser
      const audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 2048;
      source.connect(analyser);
      audioContextRef.current = audioCtx;
      analyserRef.current = analyser;
      drawWaveform();

      // Setup WebSocket
      const token = localStorage.getItem('vshield_token');
      const wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/analyze';
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;
      setWsStatus('connecting');

      ws.onopen = () => {
        setWsStatus('connected');
        ws.send(JSON.stringify({ type: 'start', token: token }));
      };

      ws.onmessage = (event) => {
        try {
          // If message is binary (float32 vad result), ignore or handle if needed
          if (event.data instanceof Blob) return;
          
          const data = JSON.parse(event.data);
          
          if (data.type === 'vad') {
            setVadStatus(data.status);
          } else if (data.type === 'analysis' && data.status === 'success') {
            setLatestAnalysis(data);
            setHistory(prev => {
              const newHist = [...prev, {
                time: new Date().toLocaleTimeString(),
                risk: data.impersonation_risk_score,
                spoof: data.spoof_probability * 100,
                similarity: data.speaker_similarity ? data.speaker_similarity * 100 : null
              }];
              return newHist.slice(-60); // Keep last 60 points
            });
          } else if (data.type === 'error') {
            console.error('WS Error:', data.message);
            // Handle auth error gracefully
            if (data.message.includes('Authentication')) {
                stopRecording();
            }
          }
        } catch (e) {
          console.error("Error parsing message", e);
        }
      };

      ws.onclose = () => {
        setWsStatus('disconnected');
        stopRecording();
      };

      // Setup MediaRecorder for 16kHz
      // Not fully supported in all browsers to set sampleRate via constraints alone
      // The backend handles resampling but we send blobs.
      const mr = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      mediaRecorderRef.current = mr;

      mr.ondataavailable = (e) => {
        if (e.data.size > 0 && ws.readyState === WebSocket.OPEN) {
          ws.send(e.data);
        }
      };
      
      // Request data every 500ms
      mr.start(500);
      setIsRecording(true);
      
    } catch (err) {
      console.error("Error accessing microphone", err);
      alert("Microphone access denied or unavailable.");
    }
  };

  // Function previously here has been moved up

  return (
    <div className="space-y-6">
      {/* Header controls */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
        <div>
          <h2 className="text-xl font-semibold text-slate-100">Live Voice Security Engine</h2>
          <p className="text-slate-400 text-sm mt-1">Real-time anti-spoofing and identity verification</p>
        </div>
        
        <button
          onClick={isRecording ? stopRecording : startRecording}
          className={`px-6 py-3 rounded-xl font-medium flex items-center gap-2 transition-all shadow-lg ${
            isRecording 
              ? 'bg-red-500 hover:bg-red-600 text-white shadow-red-500/20' 
              : 'bg-blue-600 hover:bg-blue-500 text-white shadow-blue-500/20'
          }`}
        >
          {isRecording ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
          {isRecording ? 'Stop Analysis' : 'Start Analysis'}
        </button>
      </div>

      {isRecording ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          
          {/* Main Chart Area */}
          <div className="lg:col-span-2 space-y-6">
            
            {/* Waveform Visualization */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-medium text-slate-300 flex items-center gap-2">
                  <Activity className="w-4 h-4 text-blue-400" />
                  Audio Stream
                </h3>
                <span className={`px-2 py-1 rounded text-xs font-bold uppercase tracking-wider ${
                  vadStatus === 'SPEECH' ? 'bg-blue-500/20 text-blue-400' : 'bg-slate-800 text-slate-400'
                }`}>
                  {vadStatus}
                </span>
              </div>
              <div className="h-24 bg-slate-950 rounded-xl border border-slate-800 overflow-hidden relative">
                <canvas ref={canvasRef} width={800} height={96} className="w-full h-full object-cover" />
              </div>
            </div>

            {/* Risk History Graph */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
              <h3 className="text-sm font-medium text-slate-300 mb-6">Real-Time Risk Trajectory</h3>
              <div className="h-64 w-full">
                {history.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={history} margin={{ top: 5, right: 5, left: -20, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                      <XAxis dataKey="time" stroke="#475569" fontSize={10} tickFormatter={(val) => val.split(' ')[0]} />
                      <YAxis stroke="#475569" domain={[0, 100]} fontSize={10} />
                      <Tooltip 
                        contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', color: '#f8fafc' }}
                        itemStyle={{ fontSize: 12 }}
                        labelStyle={{ fontSize: 12, color: '#94a3b8' }}
                      />
                      <ReferenceLine y={80} stroke="#ef4444" strokeDasharray="3 3" />
                      <ReferenceLine y={30} stroke="#10b981" strokeDasharray="3 3" />
                      <Line type="monotone" dataKey="risk" stroke="#3b82f6" strokeWidth={3} dot={false} isAnimationActive={false} />
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-slate-500 text-sm">
                    Waiting for data points...
                  </div>
                )}
              </div>
            </div>

          </div>

          {/* Details Sidebar */}
          <div className="col-span-1 space-y-6">
            
            {/* BIG RISK CARD */}
            <div className={`border rounded-2xl p-6 text-center shadow-xl transition-colors duration-500 ${
              latestAnalysis?.impersonation_risk_level === 'CRITICAL' ? 'bg-red-950/30 border-red-900/50 shadow-red-900/20' :
              latestAnalysis?.impersonation_risk_level === 'HIGH' ? 'bg-orange-950/30 border-orange-900/50 shadow-orange-900/20' :
              latestAnalysis?.impersonation_risk_level === 'MEDIUM' ? 'bg-yellow-950/30 border-yellow-900/50 shadow-yellow-900/20' :
              latestAnalysis ? 'bg-emerald-950/20 border-emerald-900/50 shadow-emerald-900/20' :
              'bg-slate-900 border-slate-800'
            }`}>
              <h3 className="text-xs font-bold tracking-widest text-slate-400 uppercase mb-4">Current Risk Level</h3>
              <div className="flex items-end justify-center gap-2 mb-2">
                <span className={`text-6xl font-bold tracking-tighter ${
                  latestAnalysis?.impersonation_risk_level === 'CRITICAL' ? 'text-red-400' :
                  latestAnalysis?.impersonation_risk_level === 'HIGH' ? 'text-orange-400' :
                  latestAnalysis?.impersonation_risk_level === 'MEDIUM' ? 'text-yellow-400' :
                  latestAnalysis ? 'text-emerald-400' :
                  'text-slate-200'
                }`}>
                  {latestAnalysis ? latestAnalysis.impersonation_risk_score.toFixed(1) : '--'}
                </span>
                <span className="text-xl text-slate-500 font-light mb-1">/ 100</span>
              </div>
              <div className={`inline-block px-3 py-1 rounded-full text-xs font-bold tracking-wider mt-2 ${
                  latestAnalysis?.impersonation_risk_level === 'CRITICAL' ? 'bg-red-500/20 text-red-400 border border-red-500/30' :
                  latestAnalysis?.impersonation_risk_level === 'HIGH' ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30' :
                  latestAnalysis?.impersonation_risk_level === 'MEDIUM' ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30' :
                  latestAnalysis ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' :
                  'bg-slate-800 text-slate-400'
              }`}>
                {latestAnalysis ? latestAnalysis.impersonation_risk_level : 'AWAITING DATA'}
              </div>
            </div>

            {/* Evidence & Metrics */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
              <h3 className="text-sm font-medium text-slate-300 mb-4">Inference Details</h3>
              
              <div className="space-y-4">
                <div className="flex justify-between items-center border-b border-slate-800 pb-3">
                  <span className="text-slate-400 text-sm">Spoof Probability</span>
                  <span className="text-slate-200 font-medium">
                    {latestAnalysis?.spoof_probability !== undefined 
                      ? `${(latestAnalysis.spoof_probability * 100).toFixed(1)}%` 
                      : '--'}
                  </span>
                </div>
                
                <div className="flex justify-between items-center border-b border-slate-800 pb-3">
                  <span className="text-slate-400 text-sm">Speaker Match</span>
                  <span className={`font-medium ${
                    latestAnalysis?.speaker_similarity !== undefined && latestAnalysis?.speaker_similarity !== null && latestAnalysis.speaker_similarity < 0.25 
                      ? 'text-red-400' : 'text-slate-200'
                  }`}>
                    {latestAnalysis?.speaker_similarity !== undefined && latestAnalysis?.speaker_similarity !== null 
                      ? `${(latestAnalysis.speaker_similarity * 100).toFixed(1)}%` 
                      : (latestAnalysis?.speaker_status === 'NOT_ENROLLED' ? 'No Profile' : '--')}
                  </span>
                </div>
                
                <div className="flex justify-between items-center pb-2">
                  <span className="text-slate-400 text-sm">Confidence</span>
                  <span className="text-slate-200 font-medium">{latestAnalysis?.risk_confidence || '--'}</span>
                </div>
              </div>

              {latestAnalysis?.risk_reasons && latestAnalysis.risk_reasons.length > 0 && (
                <div className="mt-4 pt-4 border-t border-slate-800">
                  <span className="text-slate-400 text-xs font-semibold uppercase tracking-wider block mb-3">Evidence</span>
                  <ul className="space-y-2">
                    {latestAnalysis.risk_reasons.map((r: string, i: number) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-slate-300 bg-slate-800/50 p-2 rounded-lg">
                        <AlertCircle className="w-4 h-4 text-orange-400 shrink-0 mt-0.5" />
                        <span>{r}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

          </div>

        </div>
      ) : (
        <div className="flex flex-col items-center justify-center py-24 bg-slate-900/50 border border-slate-800 border-dashed rounded-2xl">
          <div className="w-16 h-16 bg-blue-500/10 rounded-full flex items-center justify-center mb-4">
            <Mic className="w-8 h-8 text-blue-500" />
          </div>
          <h3 className="text-xl font-medium text-slate-200 mb-2">Ready to secure</h3>
          <p className="text-slate-400">Click Start Analysis to begin capturing and verifying audio.</p>
        </div>
      )}
    </div>
  );
};

export default LiveAnalysis;
