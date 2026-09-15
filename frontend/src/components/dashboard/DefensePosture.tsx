export interface DefensePostureProps {
  history: any[];
}

const DefensePosture = ({ history }: DefensePostureProps) => {
  const callsAnalyzed = history.length;
  const threatsIntercepted = history.filter(h => h.risk_level === 'HIGH' || h.risk_level === 'CRITICAL').length;
  const protectedScore = callsAnalyzed > 0 
    ? Math.max(0, Math.round(100 - ((threatsIntercepted / callsAnalyzed) * 100))) 
    : 100;
  
  // Convert score to stroke dashoffset (251.2 is full circle, 0 is full, 251.2 is empty)
  const offset = 251.2 - (251.2 * (protectedScore / 100));

  return (
    <div className="bg-[#0f172a] rounded-lg border border-outline-variant p-6 flex flex-col h-[400px] shadow-lg">
      <div className="flex justify-between items-start mb-6">
        <div>
          <h3 className="font-headline-sm text-on-surface text-lg font-semibold tracking-tight">Defense Posture</h3>
          <p className="font-body-sm text-[11px] text-outline mt-1 leading-tight tracking-wide">Continuous telemetry cross-validating<br/>synthetic acoustic artifacts.</p>
        </div>
        <div className="font-label-sm text-[9px] tracking-widest text-[#45e0a0] uppercase font-bold mt-1">
          REAL-TIME
        </div>
      </div>

      <div className="flex flex-col items-center justify-center mb-6 mt-2">
        <div className="relative w-[140px] h-[140px] flex items-center justify-center">
          {/* Circular Progress Ring */}
          <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
            <circle cx="50" cy="50" r="40" fill="transparent" stroke="#1e293b" strokeWidth="10" />
            <circle 
              cx="50" cy="50" r="40" 
              fill="transparent" 
              stroke="#45e0a0" 
              strokeWidth="10" 
              strokeDasharray="251.2" 
              strokeDashoffset={offset} 
              strokeLinecap="round" 
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center pb-2">
            <span className="font-headline-sm text-[2.5rem] font-bold text-on-surface leading-none mt-2">{protectedScore}</span>
            <span className="font-label-sm text-[9px] text-[#45e0a0] tracking-widest uppercase mt-1 font-bold">PROTECTED</span>
          </div>
        </div>
        <span className="font-label-sm text-[10px] text-outline mt-4">Target Compliance Baseline: 98+</span>
      </div>

      <div className="space-y-4 pt-4 mt-auto">
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-3">
            <div className="w-2 h-2 rounded-full bg-[#45e0a0]" />
            <div className="flex flex-col">
              <span className="font-body-sm text-[11px] text-on-surface leading-tight font-semibold">AI Detection Engine</span>
              <span className="font-code-sm text-[10px] text-outline leading-tight mt-0.5">Model: SpectralNet-v4.2</span>
            </div>
          </div>
          <span className="px-2 py-0.5 bg-[#45e0a0]/10 text-[#45e0a0] border border-[#45e0a0]/20 font-label-sm text-[10px] tracking-widest font-bold rounded">ACTIVE</span>
        </div>

        <div className="flex justify-between items-center">
          <div className="flex items-center gap-3">
            <div className="w-2 h-2 rounded-full bg-[#45e0a0]" />
            <div className="flex flex-col">
              <span className="font-body-sm text-[11px] text-on-surface leading-tight font-semibold">Speaker Verification</span>
              <span className="font-code-sm text-[10px] text-outline leading-tight mt-0.5">Biometric Profile Sync</span>
            </div>
          </div>
          <span className="px-2 py-0.5 bg-[#45e0a0]/10 text-[#45e0a0] border border-[#45e0a0]/20 font-label-sm text-[10px] tracking-widest font-bold rounded">CALIBRATED</span>
        </div>

        <div className="flex justify-between items-center">
          <div className="flex items-center gap-3">
            <div className="w-2 h-2 rounded-full bg-[#00c8e8]" />
            <div className="flex flex-col">
              <span className="font-body-sm text-[11px] text-on-surface leading-tight font-semibold">Audio Forensic Engine</span>
              <span className="font-code-sm text-[10px] text-outline leading-tight mt-0.5">SIP RTP Stream Proxy</span>
            </div>
          </div>
          <span className="px-2 py-0.5 text-[#00c8e8] font-label-sm text-[10px] tracking-widest font-bold">14ms Latency</span>
        </div>
        
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-3">
            <div className="w-2 h-2 rounded-full bg-[#45e0a0]" />
            <div className="flex flex-col">
              <span className="font-body-sm text-[11px] text-on-surface leading-tight font-semibold">Telemetry Ingestion</span>
              <span className="font-code-sm text-[10px] text-outline leading-tight mt-0.5">TLS 1.3 Full Duplex</span>
            </div>
          </div>
          <span className="px-2 py-0.5 bg-[#45e0a0]/10 text-[#45e0a0] border border-[#45e0a0]/20 font-label-sm text-[10px] tracking-widest font-bold rounded">CONNECTED</span>
        </div>
      </div>
    </div>
  );
};

export default DefensePosture;
