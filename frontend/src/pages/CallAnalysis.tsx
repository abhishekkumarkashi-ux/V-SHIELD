import { Play, Download, RefreshCw, AlertTriangle, Fingerprint, Activity } from 'lucide-react';
import { AreaChart, Area, XAxis, ReferenceArea, ResponsiveContainer } from 'recharts';

// Mock data for the waveform to mimic the design
const waveformData = Array.from({ length: 150 }, (_, i) => {
  const isAnomaly1 = i > 40 && i < 65;
  const isAnomaly2 = i > 120 && i < 145;
  
  let baseAmp = Math.sin(i / 2) * 30;
  if (isAnomaly1 || isAnomaly2) {
    baseAmp = (Math.sin(i * 1.5) * 45) + (Math.random() * 10 - 5);
  }
  
  return {
    time: i,
    amp: baseAmp,
    ampNeg: -baseAmp,
  };
});

const CallAnalysis = () => {
  return (
    <div className="flex flex-col w-full h-full gap-4">
      {/* Top Header Section */}
      <div className="flex flex-col gap-4">
        <div className="flex justify-between items-start">
          <div className="flex flex-col gap-1">
            <span className="font-code-sm text-[10px] text-primary tracking-widest uppercase font-bold flex items-center gap-1">
              <span className="text-outline">CALLS /</span> #VSH-8942-B <span className="text-outline">/ WIRE DESK IMPERSONATION INCIDENT</span>
            </span>
            <div className="flex items-center gap-4">
              <h1 className="font-headline-xl text-3xl text-on-surface tracking-tight font-semibold mt-1">Call Forensic Investigation</h1>
              <div className="px-3 py-1 bg-error/10 border border-error/30 rounded-full mt-1">
                <span className="font-label-sm text-[10px] text-error uppercase font-bold tracking-widest">CRITICAL THREAT TERMINATED</span>
              </div>
            </div>
          </div>
          <div className="flex flex-col gap-2 items-end">
            <div className="flex items-center gap-3">
              <button className="flex items-center gap-2 px-4 py-1.5 border border-[#00c8e8]/50 text-[#00c8e8] hover:bg-[#00c8e8]/10 transition-colors rounded font-label-sm text-[11px] uppercase tracking-wider font-bold">
                <Download className="w-3.5 h-3.5" /> Export Audio Report (PDF)
              </button>
              <button className="flex items-center gap-2 px-4 py-1.5 border border-outline-variant text-on-surface hover:bg-surface-container-high transition-colors rounded font-label-sm text-[11px] uppercase tracking-wider font-bold">
                <Download className="w-3.5 h-3.5" /> Download Unencrypted WAV
              </button>
            </div>
            <button className="flex items-center gap-2 px-4 py-1.5 border border-[#00c8e8]/50 text-[#00c8e8] bg-[#00c8e8]/5 hover:bg-[#00c8e8]/10 transition-colors rounded font-label-sm text-[11px] uppercase tracking-wider font-bold">
              <RefreshCw className="w-3.5 h-3.5" /> Re-Analyze Audio
            </button>
          </div>
        </div>

        {/* Info Grid */}
        <div className="grid grid-cols-6 gap-3">
          <div className="bg-[#0f172a] border border-outline-variant rounded p-3 flex flex-col justify-between shadow">
            <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest font-bold">CALL ID</span>
            <div className="flex flex-col mt-1">
              <span className="font-code-md text-[13px] text-[#00c8e8] font-bold">#VSH-8942-B</span>
              <span className="font-code-sm text-[10px] text-outline mt-1">SHA256: 8f92..c1a</span>
            </div>
          </div>
          <div className="bg-[#0f172a] border border-outline-variant rounded p-3 flex flex-col justify-between shadow">
            <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest font-bold">INBOUND CALLER</span>
            <div className="flex flex-col mt-1">
              <span className="font-code-md text-[13px] text-on-surface font-bold">+44 20 7946 0912</span>
              <div className="flex items-center gap-1 mt-1">
                <AlertTriangle className="w-3 h-3 text-error" />
                <span className="font-label-sm text-[10px] text-error font-bold">Spoofed PBX Gateway</span>
              </div>
            </div>
          </div>
          <div className="bg-[#0f172a] border border-outline-variant rounded p-3 flex flex-col justify-between shadow">
            <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest font-bold">RECIPIENT TARGET</span>
            <div className="flex flex-col mt-1">
              <span className="font-code-md text-[13px] text-on-surface font-bold truncate">Wire Operation...</span>
              <span className="font-label-sm text-[10px] text-outline mt-1">Tier 1 Approver (Ext 4012)</span>
            </div>
          </div>
          <div className="bg-[#0f172a] border border-outline-variant rounded p-3 flex flex-col justify-between shadow">
            <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest font-bold">DURATION</span>
            <div className="flex flex-col mt-1">
              <span className="font-code-md text-[13px] text-on-surface font-bold">02m 30s</span>
              <span className="font-label-sm text-[10px] text-[#45e0a0] font-bold mt-1">Force-Terminated</span>
            </div>
          </div>
          <div className="bg-[#0f172a] border border-outline-variant rounded p-3 flex flex-col justify-between shadow">
            <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest font-bold">TIMESTAMP</span>
            <div className="flex flex-col mt-1">
              <span className="font-code-md text-[13px] text-on-surface font-bold">14:22:15 UTC</span>
              <span className="font-label-sm text-[10px] text-outline mt-1">Oct 24, 2025</span>
            </div>
          </div>
          <div className="bg-[#0f172a] border border-outline-variant rounded p-3 flex flex-col justify-between shadow">
            <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest font-bold">CHANNEL ROUTE</span>
            <div className="flex flex-col mt-1">
              <span className="font-code-md text-[13px] text-[#00c8e8] font-bold">Frankfurt-02</span>
              <span className="font-label-sm text-[10px] text-outline mt-1">SIP Trunk TLS 1.3</span>
            </div>
          </div>
        </div>

        {/* 4 Key Metrics */}
        <div className="grid grid-cols-4 gap-4">
          {/* Card 1 */}
          <div className="bg-[#0f172a] border border-outline-variant rounded p-4 flex flex-col justify-between shadow-lg h-28 relative overflow-hidden">
            <div className="flex justify-between items-start">
              <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest font-bold">IMPERSONATION RISK</span>
              <span className="px-2 py-0.5 bg-error/10 text-error border border-error/20 font-label-sm text-[9px] tracking-widest font-bold rounded">CRITICAL ALERT</span>
            </div>
            <div className="flex flex-col">
              <div className="flex items-baseline gap-1 mt-1">
                <span className="text-[2.5rem] font-headline-sm font-bold tracking-tight text-error leading-none">87</span>
                <span className="text-xs font-label-sm text-outline font-bold">/ 100</span>
              </div>
              <div className="flex items-center gap-2 mt-2">
                <div className="w-1.5 h-1.5 rounded-full bg-error animate-pulse" />
                <span className="font-label-sm text-[10px] text-outline">Intercept threshold (75) breached</span>
              </div>
            </div>
            {/* Red glow at bottom */}
            <div className="absolute bottom-0 left-0 right-0 h-1 bg-error" />
          </div>

          {/* Card 2 */}
          <div className="bg-[#0f172a] border border-outline-variant rounded p-4 flex flex-col justify-between shadow-lg h-28 relative">
            <div className="flex justify-between items-start">
              <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest font-bold">VOICE AUTHENTICITY</span>
              <Activity className="w-4 h-4 text-error" />
            </div>
            <div className="flex flex-col">
              <div className="flex items-baseline gap-1 mt-1">
                <span className="text-[2.5rem] font-headline-sm font-bold tracking-tight text-error leading-none">12%</span>
                <span className="text-xs font-label-sm text-outline font-bold">Confidence</span>
              </div>
              <div className="flex items-center gap-2 mt-2">
                <AlertTriangle className="w-3 h-3 text-error" />
                <span className="font-label-sm text-[10px] text-error font-bold">Synthetic Artifacts Detected</span>
              </div>
            </div>
            <div className="absolute bottom-0 left-0 right-0 h-1 bg-error" />
          </div>

          {/* Card 3 */}
          <div className="bg-[#0f172a] border border-outline-variant rounded p-4 flex flex-col justify-between shadow-lg h-28 relative">
            <div className="flex justify-between items-start">
              <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest font-bold">SPEAKER MATCH</span>
              <Fingerprint className="w-4 h-4 text-error" />
            </div>
            <div className="flex flex-col">
              <div className="flex items-baseline gap-1 mt-1">
                <span className="text-[2.5rem] font-headline-sm font-bold tracking-tight text-on-surface leading-none">21%</span>
                <span className="text-xs font-label-sm text-outline font-bold">Baseline Profile</span>
              </div>
              <div className="flex items-center gap-2 mt-2">
                <div className="w-1.5 h-1.5 rounded-full bg-error" />
                <span className="font-label-sm text-[10px] text-outline">Significant Biometric Divergence</span>
              </div>
            </div>
            <div className="absolute bottom-0 left-0 right-0 h-1 bg-error" />
          </div>

          {/* Card 4 */}
          <div className="bg-[#0f172a] border border-outline-variant rounded p-4 flex flex-col justify-between shadow-lg h-28 relative">
            <div className="flex justify-between items-start">
              <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest font-bold">DEEPFAKE PROBABILITY</span>
              <span className="px-2 py-0.5 bg-[#00c8e8]/10 text-[#00c8e8] border border-[#00c8e8]/20 font-label-sm text-[9px] tracking-widest font-bold rounded">NEURAL MODEL</span>
            </div>
            <div className="flex flex-col">
              <div className="flex items-baseline gap-1 mt-1">
                <span className="text-[2.5rem] font-headline-sm font-bold tracking-tight text-on-surface leading-none">94.8%</span>
                <span className="text-xs font-label-sm text-[#00c8e8] font-bold">ElevenLabs</span>
              </div>
              <div className="flex items-center gap-2 mt-2">
                <div className="w-1.5 h-1.5 rounded-full bg-[#00c8e8]" />
                <span className="font-label-sm text-[10px] text-[#00c8e8] font-bold truncate">ElevenLabs Neural Vocoder Sig...</span>
              </div>
            </div>
            <div className="absolute bottom-0 left-0 right-0 h-1 bg-[#00c8e8]" />
          </div>
        </div>

        {/* Waveform Section */}
        <div className="bg-[#0f172a] border border-outline-variant rounded p-6 shadow-lg flex flex-col gap-4">
          <div className="flex justify-between items-center mb-2">
             <div className="flex items-center gap-4">
               <Activity className="w-5 h-5 text-[#00c8e8]" />
               <h3 className="font-headline-sm text-lg text-on-surface font-semibold tracking-tight">Dual-Track Acoustic Waveform & Spectral Density</h3>
             </div>
             <div className="flex items-center gap-6">
               <span className="font-code-sm text-[10px] text-outline">48kHz / 24-Bit Linear PCM</span>
               <button className="flex items-center gap-2 bg-[#00c8e8]/10 text-[#00c8e8] px-3 py-1.5 rounded font-label-sm text-[10px] uppercase tracking-wider font-bold hover:bg-[#00c8e8]/20 transition-colors">
                 <Play className="w-3 h-3" /> Play Anomaly Window
               </button>
               <span className="font-code-sm text-xs font-bold text-[#00c8e8]">00:42.15 <span className="text-outline">/ 02:30.00</span></span>
             </div>
          </div>

          <div className="flex justify-between items-center mb-1">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-[#00c8e8]" />
              <span className="font-label-sm text-[10px] text-on-surface font-bold uppercase tracking-wider">CH-1: Inbound Audio Amplitude</span>
              <span className="font-code-sm text-[9px] text-outline border-l border-outline-variant pl-2 ml-1">Bandpass 300Hz-3.4kHz</span>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-error" />
                <span className="font-label-sm text-[10px] text-error font-bold uppercase tracking-wider">Flagged Synthesis Window</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-2 h-0.5 bg-[#00c8e8]" />
                <span className="font-label-sm text-[10px] text-[#00c8e8] font-bold uppercase tracking-wider">Baseline Target VAD</span>
              </div>
            </div>
          </div>

          <div className="w-full h-[200px] bg-[#1e293b]/50 border border-outline-variant/30 rounded relative flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
               <AreaChart data={waveformData} margin={{ top: 20, right: 0, left: 0, bottom: 0 }}>
                 <defs>
                   <linearGradient id="colorWave" x1="0" y1="0" x2="0" y2="1">
                     <stop offset="5%" stopColor="#00c8e8" stopOpacity={0.8}/>
                     <stop offset="95%" stopColor="#00c8e8" stopOpacity={0.3}/>
                   </linearGradient>
                 </defs>
                 
                 {/* X Axis mock */}
                 <XAxis hide dataKey="time" />
                 
                 {/* Anomaly 1 */}
                 <ReferenceArea x1={40} x2={65} fill="#ffaaa0" fillOpacity={0.15} stroke="#ffaaa0" strokeOpacity={0.5} />
                 {/* Anomaly 2 */}
                 <ReferenceArea x1={120} x2={145} fill="#ffaaa0" fillOpacity={0.15} stroke="#ffaaa0" strokeOpacity={0.5} />
                 
                 <Area type="step" dataKey="amp" stroke="#00c8e8" fill="url(#colorWave)" isAnimationActive={false} />
                 <Area type="step" dataKey="ampNeg" stroke="#00c8e8" fill="url(#colorWave)" isAnimationActive={false} />
               </AreaChart>
            </ResponsiveContainer>
            
            {/* Custom Overlay Texts for the Reference Areas */}
            <div className="absolute top-2 left-[30%] bg-error/20 border border-error px-2 py-0.5 rounded">
               <span className="font-code-sm text-[8px] text-error uppercase font-bold tracking-widest">SYNTHETIC PHASE DISCONTINUITY</span>
            </div>
            <div className="absolute top-2 right-[8%] bg-error/20 border border-error px-2 py-0.5 rounded">
               <span className="font-code-sm text-[8px] text-error uppercase font-bold tracking-widest">NEURAL MODEL CLONE ESCALATION</span>
            </div>

            {/* Timestamps overlay */}
            <div className="absolute bottom-2 inset-x-4 flex justify-between font-code-sm text-[9px] text-outline/50 pointer-events-none">
              <span>00:00</span>
              <span>00:25</span>
              <span>00:50</span>
              <span>01:15</span>
              <span>01:40</span>
              <span>02:05</span>
              <span>02:30 (CUT)</span>
            </div>
          </div>
        </div>

        {/* Interactive Threat Timeline */}
        <div className="bg-[#0f172a] border border-outline-variant rounded p-5 shadow-lg flex flex-col gap-4">
          <div className="flex justify-between items-center mb-2">
            <div className="flex flex-col">
              <h3 className="font-headline-sm text-sm text-on-surface font-semibold">Interactive Call Threat Timeline</h3>
              <span className="font-label-sm text-[10px] text-outline mt-1 tracking-wide">Chronological incident reconstruction with correlated acoustic telemetry</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-1.5 h-1.5 rounded-full bg-error" />
              <span className="font-label-sm text-[10px] text-on-surface font-bold uppercase tracking-wider">6 Critical Forensic Flags</span>
            </div>
          </div>

          <div className="grid grid-cols-4 gap-4 mt-2">
            <div className="flex flex-col gap-2 border-t-2 border-outline-variant pt-3 relative">
               <div className="absolute top-[-5px] left-0 w-2 h-2 rounded-full bg-outline-variant" />
               <div className="flex justify-between">
                 <span className="font-code-sm text-[11px] text-[#00c8e8] font-bold">00:00</span>
                 <span className="px-1.5 py-0.5 bg-surface-container border border-outline-variant rounded font-label-sm text-[8px] uppercase tracking-widest text-outline">INBOUND HANDSHAKE</span>
               </div>
               <span className="font-body-sm text-xs text-on-surface font-bold">Call Initiated via VoIP Trunk</span>
            </div>

            <div className="flex flex-col gap-2 border-t-2 border-outline-variant pt-3 relative">
               <div className="absolute top-[-5px] left-0 w-2 h-2 rounded-full bg-outline-variant" />
               <div className="flex justify-between">
                 <span className="font-code-sm text-[11px] text-[#00c8e8] font-bold">00:17</span>
                 <span className="px-1.5 py-0.5 bg-surface-container border border-outline-variant rounded font-label-sm text-[8px] uppercase tracking-widest text-outline">VAD SENSOR</span>
               </div>
               <span className="font-body-sm text-xs text-on-surface font-bold">Human Voice Activity Detected</span>
            </div>

            <div className="flex flex-col gap-2 border-t-2 border-error pt-3 relative">
               <div className="absolute top-[-5px] left-0 w-2 h-2 rounded-full bg-error" />
               <div className="flex justify-between">
                 <span className="font-code-sm text-[11px] text-error font-bold">00:42</span>
                 <span className="px-1.5 py-0.5 bg-error/10 border border-error/30 rounded font-label-sm text-[8px] uppercase tracking-widest text-error font-bold">ACOUSTIC GLITCH</span>
               </div>
               <span className="font-body-sm text-xs text-error font-bold">Acoustic Anomaly Detected</span>
            </div>
            
            <div className="flex flex-col gap-2 border-t-2 border-error pt-3 relative opacity-50 pointer-events-none">
               <div className="absolute top-[-5px] left-0 w-2 h-2 rounded-full bg-error" />
               <div className="flex justify-between">
                 <span className="font-code-sm text-[11px] text-error font-bold">01:14</span>
                 <span className="px-1.5 py-0.5 bg-error/10 border border-error/30 rounded font-label-sm text-[8px] uppercase tracking-widest text-error font-bold">NEURAL SPIKE</span>
               </div>
               <span className="font-body-sm text-xs text-error font-bold">Cloned Voice Confirmed</span>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
};

export default CallAnalysis;
