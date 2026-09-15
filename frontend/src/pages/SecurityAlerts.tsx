import { CheckCheck, SlidersHorizontal, Power, Search, ShieldCheck, AlertCircle, XCircle, PhoneOff, LayoutGrid, List } from 'lucide-react';
import { AreaChart, Area, ResponsiveContainer } from 'recharts';

const mockFftData = [
  { time: 1, val: 20 }, { time: 2, val: 25 }, { time: 3, val: 18 },
  { time: 4, val: 35 }, { time: 5, val: 30 }, { time: 6, val: 40 },
  { time: 7, val: 38 }, { time: 8, val: 80 }, { time: 9, val: 85 },
  { time: 10, val: 90 }, { time: 11, val: 82 }, { time: 12, val: 30 }
];

const SecurityAlerts = () => {
  return (
    <div className="flex flex-col w-full h-full gap-4 pb-10">
      {/* Header Section */}
      <div className="flex flex-col gap-4 border-b border-outline-variant/50 pb-5">
        <div className="flex justify-between items-start">
          <div className="flex flex-col gap-1">
            <span className="font-code-sm text-[10px] text-error tracking-widest uppercase font-bold flex items-center gap-1">
              TRIAGE LIVE MODE <span className="text-outline">INCIDENT QUEUE ID: SEC-TRI-994</span>
            </span>
            <h1 className="font-headline-xl text-3xl text-on-surface tracking-tight font-semibold mt-1">Security Alerts</h1>
            <p className="font-body-sm text-sm text-outline mt-1 leading-relaxed max-w-2xl">
              Active voice threat detections requiring analyst review, acoustic vector corroboration,<br/>and rapid operational intervention.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button className="flex items-center gap-2 px-4 py-2 border border-outline-variant text-on-surface hover:bg-surface-container-high transition-colors rounded font-label-sm text-[11px] uppercase tracking-wider font-bold">
              <CheckCheck className="w-4 h-4 text-[#45e0a0]" /> Mark All as Read
            </button>
            <button className="flex items-center gap-2 px-4 py-2 border border-outline-variant text-on-surface hover:bg-surface-container-high transition-colors rounded font-label-sm text-[11px] uppercase tracking-wider font-bold">
              <SlidersHorizontal className="w-4 h-4" /> Alert Notification Settings
            </button>
          </div>
        </div>

        {/* 4 Severity Cards */}
        <div className="grid grid-cols-4 gap-4 mt-2">
          {/* CRITICAL */}
          <div className="bg-[#0f172a] border border-error/30 rounded p-4 flex flex-col justify-between shadow-lg h-32 relative overflow-hidden">
            <div className="absolute top-0 left-0 right-0 h-1 bg-error" />
            <div className="flex justify-between items-start">
              <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest font-bold">CRITICAL SEVERITY</span>
              <div className="p-1.5 rounded bg-error/10 border border-error/20"><Power className="w-4 h-4 text-error" /></div>
            </div>
            <div className="flex items-baseline gap-1 mt-1">
              <span className="text-[2.5rem] font-headline-sm font-bold tracking-tight text-error leading-none">3</span>
              <span className="text-xs font-label-sm text-on-surface font-bold">Active</span>
            </div>
            <div className="flex items-center justify-between mt-2 pt-2 border-t border-error/20">
              <span className="font-label-sm text-[9px] text-error bg-error/10 px-1.5 py-0.5 rounded font-bold uppercase tracking-widest">IMMEDIATE INTERCEPT</span>
              <span className="font-code-sm text-[10px] text-outline">SLA: 02m 45s</span>
            </div>
          </div>
          {/* HIGH */}
          <div className="bg-[#0f172a] border border-[#facc15]/30 rounded p-4 flex flex-col justify-between shadow-lg h-32 relative overflow-hidden">
            <div className="absolute top-0 left-0 right-0 h-1 bg-[#facc15]" />
            <div className="flex justify-between items-start">
              <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest font-bold">HIGH SEVERITY</span>
              <div className="p-1.5 rounded bg-[#facc15]/10 border border-[#facc15]/20 text-[#facc15] font-bold text-xs px-2">!</div>
            </div>
            <div className="flex items-baseline gap-1 mt-1">
              <span className="text-[2.5rem] font-headline-sm font-bold tracking-tight text-[#facc15] leading-none">8</span>
              <span className="text-xs font-label-sm text-on-surface font-bold">Pending</span>
            </div>
            <div className="flex items-center justify-between mt-2 pt-2 border-t border-[#facc15]/20">
              <span className="font-label-sm text-[9px] text-[#facc15] bg-[#facc15]/10 px-1.5 py-0.5 rounded font-bold uppercase tracking-widest">REVIEW REQUIRED</span>
              <span className="font-code-sm text-[10px] text-outline">Avg Resp: 12m</span>
            </div>
          </div>
          {/* MEDIUM */}
          <div className="bg-[#0f172a] border border-[#00c8e8]/30 rounded p-4 flex flex-col justify-between shadow-lg h-32 relative overflow-hidden">
            <div className="absolute top-0 left-0 right-0 h-1 bg-[#00c8e8]" />
            <div className="flex justify-between items-start">
              <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest font-bold">MEDIUM SEVERITY</span>
              <div className="p-1.5 rounded bg-[#00c8e8]/10 border border-[#00c8e8]/20"><Search className="w-4 h-4 text-[#00c8e8]" /></div>
            </div>
            <div className="flex items-baseline gap-1 mt-1">
              <span className="text-[2.5rem] font-headline-sm font-bold tracking-tight text-on-surface leading-none">14</span>
              <span className="text-xs font-label-sm text-on-surface font-bold">Monitored</span>
            </div>
            <div className="flex items-center justify-between mt-2 pt-2 border-t border-[#00c8e8]/20">
              <span className="font-label-sm text-[9px] text-[#00c8e8] bg-[#00c8e8]/10 px-1.5 py-0.5 rounded font-bold uppercase tracking-widest">UNDER SENSOR WATCH</span>
              <span className="font-code-sm text-[10px] text-outline">Auto-scoring</span>
            </div>
          </div>
          {/* LOW */}
          <div className="bg-[#0f172a] border border-[#45e0a0]/30 rounded p-4 flex flex-col justify-between shadow-lg h-32 relative overflow-hidden">
            <div className="absolute top-0 left-0 right-0 h-1 bg-[#45e0a0]" />
            <div className="flex justify-between items-start">
              <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest font-bold">LOW / RESOLVED</span>
              <div className="p-1.5 rounded bg-[#45e0a0]/10 border border-[#45e0a0]/20"><ShieldCheck className="w-4 h-4 text-[#45e0a0]" /></div>
            </div>
            <div className="flex items-baseline gap-1 mt-1">
              <span className="text-[2.5rem] font-headline-sm font-bold tracking-tight text-[#45e0a0] leading-none">42</span>
              <span className="text-xs font-label-sm text-on-surface font-bold">Cleared</span>
            </div>
            <div className="flex items-center justify-between mt-2 pt-2 border-t border-[#45e0a0]/20">
              <span className="font-label-sm text-[9px] text-[#45e0a0] bg-[#45e0a0]/10 px-1.5 py-0.5 rounded font-bold uppercase tracking-widest">24H SAFE BASELINE</span>
              <span className="font-code-sm text-[10px] text-outline">99.8% Precision</span>
            </div>
          </div>
        </div>

        {/* Toolbar */}
        <div className="flex items-center justify-between mt-2">
          <div className="flex items-center gap-1 font-label-sm text-[11px] font-bold tracking-wider">
            <button className="px-4 py-2 bg-[#00c8e8] text-[#0f172a] rounded">All Alerts (25)</button>
            <button className="px-4 py-2 text-outline hover:text-on-surface transition-colors">Unresolved (11)</button>
            <button className="px-4 py-2 text-outline hover:text-on-surface transition-colors">Assigned to Me (4)</button>
            <button className="px-4 py-2 text-outline hover:text-on-surface transition-colors">Resolved Today (14)</button>
          </div>
          <div className="flex items-center gap-4">
             <div className="flex items-center gap-2 font-label-sm text-[10px] text-outline uppercase tracking-widest font-bold">
               SORT BY:
               <select className="bg-[#1e293b] border border-outline-variant rounded px-2 py-1 text-on-surface outline-none focus:border-primary ml-1">
                 <option>Highest Risk Score</option>
                 <option>Newest First</option>
               </select>
             </div>
             <div className="flex bg-[#1e293b] rounded border border-outline-variant p-0.5">
                <button className="p-1 rounded bg-surface-container"><List className="w-4 h-4 text-[#00c8e8]" /></button>
                <button className="p-1 rounded text-outline"><LayoutGrid className="w-4 h-4" /></button>
             </div>
          </div>
        </div>
      </div>

      {/* Alerts List */}
      <div className="flex flex-col gap-5 mt-2">
        {/* Critical Alert Card */}
        <div className="bg-[#0f172a] border border-error/50 rounded-lg p-5 shadow-[0_0_20px_rgba(239,68,68,0.1)] relative">
           <div className="absolute top-0 left-0 w-1 h-full bg-error rounded-l-lg" />
           <div className="flex justify-between items-start mb-4">
             <div className="flex items-center gap-2 font-label-sm text-[10px] font-bold tracking-widest uppercase">
               <div className="px-2 py-0.5 bg-error/20 text-error rounded flex items-center gap-1">
                 <div className="w-1.5 h-1.5 rounded-full bg-error" /> CRITICAL ALERT
               </div>
               <span className="text-outline">INC-40982-SYN • </span>
               <span className="text-error flex items-center gap-1">((•)) STREAM LIVE</span>
             </div>
             <div className="flex items-center gap-4">
                <div className="flex items-center gap-1 font-headline-sm text-error">
                  <span className="text-xs text-outline font-bold uppercase tracking-widest mr-1">RISK SCORE</span>
                  <span className="text-2xl font-bold leading-none">88</span><span className="text-xs text-outline">/100</span>
                </div>
                <span className="font-code-sm text-[11px] text-outline flex items-center gap-1"><AlertCircle className="w-3 h-3"/> 3 minutes ago</span>
             </div>
           </div>

           <div className="grid grid-cols-12 gap-6">
              <div className="col-span-8 flex flex-col gap-4">
                 <h2 className="font-headline-sm text-xl text-on-surface font-semibold tracking-tight">Potential CEO Voice Impersonation Detected</h2>
                 <div className="flex items-center gap-6 font-code-sm text-[11px] text-outline">
                    <span className="flex items-center gap-1">📞 Caller: <span className="text-on-surface font-bold">+44 20 7946 0912</span> <span className="bg-error/10 text-error px-1 rounded text-[9px]">SPOOFED_CARRIER</span></span>
                    <span className="flex items-center gap-1">🖥️ Target Channel: <span className="text-[#00c8e8] font-bold">Wire Transfer Operations Desk</span></span>
                    <span className="flex items-center gap-1">👤 Claimed Identity: <span className="text-on-surface font-bold">David Richardson (CFO)</span></span>
                 </div>
                 
                 <div className="bg-[#1e293b]/50 border border-outline-variant/50 rounded p-4 mt-2">
                    <div className="flex justify-between items-center mb-3">
                       <span className="font-label-sm text-[10px] text-error font-bold uppercase tracking-widest flex items-center gap-2">
                         <div className="w-4 h-4 bg-error/20 rounded flex items-center justify-center border border-error/50">⚡</div> FORENSIC VECTOR CORROBORATION
                       </span>
                       <span className="font-code-sm text-[11px] text-[#00c8e8] font-bold uppercase">CONFIDENCE: 98.6%</span>
                    </div>
                    <div className="flex flex-col gap-3">
                       <div className="flex gap-3 items-start">
                          <XCircle className="w-4 h-4 text-error shrink-0 mt-0.5" />
                          <p className="font-body-sm text-[13px] text-on-surface leading-snug">Speaker biometric mismatch against verified David Richardson profile <span className="text-error">(Cosine distance: 0.18 baseline minimum 0.85).</span></p>
                       </div>
                       <div className="flex gap-3 items-start">
                          <XCircle className="w-4 h-4 text-error shrink-0 mt-0.5" />
                          <p className="font-body-sm text-[13px] text-on-surface leading-snug">ElevenLabs neural vocoder artifacts detected at high-band 16kHz spectral signature with phase discontinuity.</p>
                       </div>
                       <div className="flex gap-3 items-start">
                          <XCircle className="w-4 h-4 text-error shrink-0 mt-0.5" />
                          <p className="font-body-sm text-[13px] text-on-surface leading-snug">High acoustic impersonation probability (98.6%) combined with aggressive urgency syntax patterns regarding authorization bypass.</p>
                       </div>
                    </div>
                 </div>

                 <div className="flex items-center gap-3 mt-2">
                    <button className="flex items-center gap-2 bg-error/10 text-error border border-error/30 hover:bg-error/20 px-5 py-2.5 rounded font-label-sm text-xs font-bold uppercase tracking-wider transition-colors">
                      <PhoneOff className="w-4 h-4" /> Terminate Call Session
                    </button>
                    <button className="flex items-center gap-2 bg-[#00c8e8] text-[#0f172a] hover:bg-[#00c8e8]/90 px-5 py-2.5 rounded font-label-sm text-xs font-bold uppercase tracking-wider transition-colors">
                      Investigate Call
                    </button>
                    <button className="flex items-center gap-2 text-outline hover:text-on-surface px-4 py-2 rounded font-label-sm text-xs font-bold transition-colors">
                      👎 Dismiss False Positive
                    </button>
                 </div>
              </div>
              
              <div className="col-span-4 flex flex-col items-end justify-between h-full py-2">
                 <div className="w-full bg-[#1e293b]/50 border border-outline-variant/30 rounded p-4 mt-8">
                    <div className="flex justify-between items-center mb-2">
                      <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest font-bold">FFT AUDIO SPECTRUM</span>
                      <span className="font-code-sm text-[9px] text-error flex items-center gap-1"><div className="w-1.5 h-1.5 rounded-full bg-error animate-pulse"/> SYNTHETIC_PEAK_16KHZ</span>
                    </div>
                    <div className="h-20 w-full relative -ml-2 mb-2">
                       <ResponsiveContainer width="100%" height="100%">
                         <AreaChart data={mockFftData}>
                           <Area type="monotone" dataKey="val" stroke="#00c8e8" fill="transparent" strokeWidth={2} isAnimationActive={false} />
                         </AreaChart>
                       </ResponsiveContainer>
                       {/* Overlay dashed bars for artifact */}
                       <div className="absolute right-4 inset-y-0 w-1/3 flex items-end justify-around pb-1">
                          <div className="w-1 bg-error/50 border border-error border-dashed h-[80%]" />
                          <div className="w-1 bg-error/50 border border-error border-dashed h-[85%]" />
                          <div className="w-1 bg-error/50 border border-error border-dashed h-[90%]" />
                          <div className="w-1 bg-error/50 border border-error border-dashed h-[82%]" />
                       </div>
                       <div className="absolute right-4 bottom-[-10px] w-1/3 text-center">
                          <span className="font-label-sm text-[7px] text-error uppercase font-bold tracking-widest bg-[#0f172a] px-1">ARTIFACT DETECTED</span>
                       </div>
                    </div>
                    <div className="flex justify-between items-center mt-4 border-t border-outline-variant/30 pt-2 font-code-sm text-[10px] text-outline">
                       <span>Payload: SIP/G.711u</span>
                       <span>Target Ext: 4091</span>
                    </div>
                 </div>
                 
                 <div className="flex items-center gap-2 font-label-sm text-[10px] text-outline font-bold mt-4">
                    Assigned: C. Mercer
                    <div className="w-6 h-6 rounded-full bg-[#00c8e8]/20 text-[#00c8e8] flex items-center justify-center text-xs">CM</div>
                    <span className="ml-2">⋮</span>
                 </div>
              </div>
           </div>
        </div>

        {/* High Severity Alert Card */}
        <div className="bg-[#0f172a] border border-[#facc15]/30 rounded-lg p-5 shadow relative">
           <div className="absolute top-0 left-0 w-1 h-full bg-[#facc15] rounded-l-lg" />
           <div className="flex justify-between items-start mb-4">
             <div className="flex items-center gap-2 font-label-sm text-[10px] font-bold tracking-widest uppercase">
               <div className="px-2 py-0.5 bg-[#facc15]/20 text-[#facc15] rounded flex items-center gap-1">
                 <div className="w-1.5 h-1.5 rounded-full bg-[#facc15]" /> HIGH SEVERITY
               </div>
               <span className="text-outline">INC-40971-SPOOF • </span>
               <span className="text-[#facc15] flex items-center gap-1">🔒 ACTIVE SESSION (04m 12s)</span>
             </div>
             <div className="flex items-center gap-4">
                <div className="flex items-center gap-1 font-headline-sm text-[#facc15]">
                  <span className="text-xs text-outline font-bold uppercase tracking-widest mr-1">RISK SCORE</span>
                  <span className="text-2xl font-bold leading-none">74</span><span className="text-xs text-outline">/100</span>
                </div>
                <span className="font-code-sm text-[11px] text-outline flex items-center gap-1"><AlertCircle className="w-3 h-3"/> 14 minutes ago</span>
             </div>
           </div>

           <div className="grid grid-cols-12 gap-6">
              <div className="col-span-8 flex flex-col gap-3">
                 <h2 className="font-headline-sm text-xl text-on-surface font-semibold tracking-tight">IT Helpdesk Password Reset Voice Spoof</h2>
                 <div className="flex items-center gap-6 font-code-sm text-[11px] text-outline mb-1">
                    <span className="flex items-center gap-1">📞 Caller: <span className="text-on-surface font-bold">+1 (312) 555-0199</span></span>
                    <span className="flex items-center gap-1">🖥️ Target: <span className="text-[#00c8e8] font-bold">Global Helpdesk Tier 2</span></span>
                    <span className="flex items-center gap-1">👤 Claimed Employee: <span className="text-on-surface font-bold">Elena Rostova (ID #9042)</span></span>
                 </div>
                 
                 <div className="flex items-center justify-between font-label-sm text-[10px] text-[#facc15] font-bold uppercase tracking-widest mt-2 border-t border-outline-variant/30 pt-3">
                    <span className="flex items-center gap-1"><CheckCheck className="w-3 h-3" /> ACOUSTIC INCONSISTENCY INDICATORS</span>
                    <span>TTS GLOTTAL LATENCY: +340MS</span>
                 </div>
              </div>
              
              <div className="col-span-4 border-l border-outline-variant/50 pl-6 flex flex-col gap-2">
                 <div className="flex justify-between items-center mb-1">
                   <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest font-bold">ACTIONABLE IMPACT</span>
                   <span className="px-1.5 py-0.5 bg-[#facc15]/10 text-[#facc15] font-code-sm text-[10px] border border-[#facc15]/30 rounded">Okta Token Reset</span>
                 </div>
                 <div className="flex justify-between items-center">
                   <span className="font-label-sm text-[10px] text-outline">Account Status:</span>
                   <span className="font-label-sm text-[10px] text-[#facc15] font-bold">Flagged for Hold</span>
                 </div>
                 <div className="flex justify-between items-center">
                   <span className="font-label-sm text-[10px] text-outline">Caller Geo-IP:</span>
                   <span className="font-label-sm text-[10px] text-on-surface font-bold">Frankfurt, DE (VPN)</span>
                 </div>
                 <div className="flex justify-between items-center">
                   <span className="font-label-sm text-[10px] text-outline">Assigned Agent:</span>
                   <span className="font-label-sm text-[10px] text-on-surface font-bold">T. Bradley (#488)</span>
                 </div>
              </div>
           </div>
        </div>

      </div>
    </div>
  );
};

export default SecurityAlerts;
