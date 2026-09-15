import { Search, Calendar, SlidersHorizontal, Table as TableIcon, RefreshCw, X, ShieldCheck, Download, Pause, RotateCcw, AlertTriangle } from 'lucide-react';
import { ResponsiveContainer, AreaChart, Area } from 'recharts';

const mockWaveformData = Array.from({ length: 50 }, (_, i) => ({
  val: Math.sin(i / 1.5) * (Math.random() * 20 + 10) + (i > 20 && i < 35 ? Math.random() * 40 : 0)
}));

const CallHistory = () => {
  return (
    <div className="flex flex-col w-full h-full gap-4 pb-6">
      {/* Header Section */}
      <div className="flex flex-col gap-4 border-b border-outline-variant/50 pb-5">
        <div className="flex justify-between items-start">
          <div className="flex flex-col gap-1">
            <span className="font-code-sm text-[10px] text-primary tracking-widest uppercase font-bold flex items-center gap-1">
              FORENSIC TELEMETRY LEDGER <span className="text-outline">/ v2.14.8-audit</span>
            </span>
            <h1 className="font-headline-xl text-3xl text-on-surface tracking-tight font-semibold mt-1">Call History</h1>
            <p className="font-body-sm text-sm text-outline mt-1">Auditable ledger of all analyzed voice streams, caller identities, and threat telemetry.</p>
          </div>
          <div className="flex items-center gap-3">
            <button className="flex items-center gap-2 px-4 py-2 border border-[#45e0a0]/50 text-[#45e0a0] hover:bg-[#45e0a0]/10 transition-colors rounded font-label-sm text-[11px] uppercase tracking-wider font-bold">
              <ShieldCheck className="w-4 h-4" /> Tamper-Proof SHA256 Sync
            </button>
            <button className="flex items-center gap-2 px-4 py-2 bg-[#00c8e8] text-[#0f172a] hover:bg-[#00c8e8]/90 transition-colors rounded font-label-sm text-[11px] uppercase tracking-wider font-bold">
              Batch Forensics Export
            </button>
            <button className="flex items-center gap-2 px-4 py-2 border border-outline-variant text-on-surface hover:bg-surface-container-high transition-colors rounded font-label-sm text-[11px] uppercase tracking-wider font-bold">
              <Download className="w-4 h-4" /> Export Ledger (CSV)
            </button>
          </div>
        </div>

        {/* Filters Section */}
        <div className="flex items-center gap-3 mt-2">
           <div className="relative flex-1">
             <Search className="w-4 h-4 text-outline absolute left-3 top-1/2 -translate-y-1/2" />
             <input type="text" placeholder="Search caller ANI, call ID, transcript snippet, or target" className="w-full bg-[#0f172a] border border-outline-variant rounded py-2 pl-9 pr-3 text-sm text-on-surface focus:outline-none focus:border-primary placeholder-outline/50" />
           </div>
           
           <div className="flex flex-col gap-1">
             <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest font-bold px-1">DATE RANGE</span>
             <button className="flex items-center justify-between gap-4 px-3 py-1.5 border border-outline-variant rounded bg-[#0f172a] text-xs font-bold w-36">
               Last 30 Days <Calendar className="w-3.5 h-3.5 text-outline" />
             </button>
           </div>
           
           <div className="flex flex-col gap-1">
             <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest font-bold px-1">RISK THRESHOLD</span>
             <button className="flex items-center justify-between gap-4 px-3 py-1.5 border border-outline-variant rounded bg-[#0f172a] text-xs font-bold w-32">
               All Risks (&gt;0) <SlidersHorizontal className="w-3.5 h-3.5 text-outline" />
             </button>
           </div>
           
           <div className="flex flex-col gap-1">
             <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest font-bold px-1">STATUS FILTER</span>
             <button className="flex items-center justify-between gap-4 px-3 py-1.5 border border-outline-variant rounded bg-[#0f172a] text-xs font-bold w-32">
               Flagged & Verif... <SlidersHorizontal className="w-3.5 h-3.5 text-outline" />
             </button>
           </div>
           
           <div className="flex flex-col gap-1">
             <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest font-bold px-1">INGRESS SIP TRUNK</span>
             <button className="flex items-center justify-between gap-4 px-3 py-1.5 border border-outline-variant rounded bg-[#0f172a] text-xs font-bold w-32">
               All SIP Trunks <SlidersHorizontal className="w-3.5 h-3.5 text-outline" />
             </button>
           </div>
        </div>
        
        {/* Active Filters Row */}
        <div className="flex items-center justify-between">
           <div className="flex items-center gap-3">
             <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest font-bold">ACTIVE FILTERS:</span>
             <div className="flex items-center gap-1.5 px-2 py-1 bg-error/20 border border-error/30 text-error rounded font-label-sm text-[10px] font-bold tracking-wider cursor-pointer">
               Risk &gt; 50 <X className="w-3 h-3" />
             </div>
             <div className="flex items-center gap-1.5 px-2 py-1 bg-[#00c8e8]/20 border border-[#00c8e8]/30 text-[#00c8e8] rounded font-label-sm text-[10px] font-bold tracking-wider cursor-pointer">
               Status: Investigated <X className="w-3 h-3" />
             </div>
             <button className="font-label-sm text-[10px] text-outline font-bold underline ml-2 hover:text-on-surface">Clear all filters</button>
           </div>
           <div className="flex items-center gap-4 font-code-sm text-[11px]">
             <span className="flex items-center gap-1 text-error font-bold"><div className="w-1.5 h-1.5 rounded-full bg-error animate-pulse"/> 14 Critical Threats Flagged</span>
             <span className="text-outline border-l border-outline-variant pl-4">Acoustic Drift Latency: <span className="text-[#00c8e8] font-bold">11ms</span></span>
           </div>
        </div>
      </div>

      <div className="flex gap-4 flex-1 mt-2 min-h-[500px]">
         {/* Main Table Area */}
         <div className="flex-1 flex flex-col border border-outline-variant rounded-lg bg-[#0f172a] overflow-hidden shadow-lg">
            <div className="flex items-center gap-4 p-4 border-b border-outline-variant/50 bg-[#1e293b]/30">
               <div className="flex items-center gap-2">
                 <TableIcon className="w-4 h-4 text-[#00c8e8]" />
                 <h3 className="font-headline-sm text-[15px] font-semibold text-on-surface tracking-tight">Voice Ingress Stream Ledger</h3>
               </div>
               <span className="font-label-sm text-[11px] text-outline font-bold">1,420 Total Records</span>
               <div className="ml-auto flex items-center gap-2 font-code-sm text-[10px] text-outline">
                 <RefreshCw className="w-3 h-3" /> Live Polling: 3s
               </div>
            </div>

            <div className="flex-1 overflow-auto">
               <table className="w-full text-left border-collapse">
                 <thead className="bg-[#1e293b]/50 sticky top-0 z-10 font-label-sm text-[10px] text-outline uppercase tracking-widest">
                   <tr>
                     <th className="p-3 pl-6 font-bold border-b border-outline-variant/50">TIMESTAMP</th>
                     <th className="p-3 font-bold border-b border-outline-variant/50">CALL ID</th>
                     <th className="p-3 font-bold border-b border-outline-variant/50">CALLER ANI / ORIGIN</th>
                     <th className="p-3 font-bold border-b border-outline-variant/50">TARGET DESK / ENDPOINT</th>
                     <th className="p-3 font-bold border-b border-outline-variant/50">DURATION</th>
                     <th className="p-3 font-bold border-b border-outline-variant/50">RISK</th>
                   </tr>
                 </thead>
                 <tbody className="font-code-sm text-[11px]">
                   {/* Row 1 - Active */}
                   <tr className="bg-[#1e293b]/80 border-b border-outline-variant/30 cursor-pointer relative shadow-[inset_2px_0_0_0_#ef4444]">
                     <td className="p-4 pl-6 text-on-surface font-bold">Oct 24, 14:22:15</td>
                     <td className="p-4 text-[#00c8e8] font-bold flex items-center gap-1"><div className="w-1.5 h-1.5 rounded-full bg-[#00c8e8]" /> #VSH-9402</td>
                     <td className="p-4">
                       <div className="flex flex-col">
                         <span className="text-on-surface font-bold">+44 20 7946 0912</span>
                         <span className="text-outline text-[9px] mt-0.5">VoIP UK (London PBX)</span>
                       </div>
                     </td>
                     <td className="p-4 text-on-surface font-bold">Wire Operations</td>
                     <td className="p-4 text-outline">02:30</td>
                     <td className="p-4">
                       <span className="px-2 py-1 bg-error/20 text-error rounded text-[10px] font-bold border border-error/30">88 C</span>
                     </td>
                   </tr>
                   {/* Row 2 */}
                   <tr className="border-b border-outline-variant/30 hover:bg-[#1e293b]/30 cursor-pointer transition-colors">
                     <td className="p-4 pl-6 text-outline">Oct 24, 14:18:40</td>
                     <td className="p-4 text-[#00c8e8] font-bold flex items-center gap-1"><div className="w-1.5 h-1.5 rounded-full bg-[#00c8e8]" /> #VSH-9398</td>
                     <td className="p-4">
                       <div className="flex flex-col">
                         <span className="text-on-surface font-bold">+1 (312) 555-0199</span>
                         <span className="text-outline text-[9px] mt-0.5">US Cellular (Chicago)</span>
                       </div>
                     </td>
                     <td className="p-4 text-on-surface font-bold">IT Helpdesk Privileged</td>
                     <td className="p-4 text-outline">04:12</td>
                     <td className="p-4">
                       <span className="px-2 py-1 bg-[#facc15]/20 text-[#facc15] rounded text-[10px] font-bold border border-[#facc15]/30">74 H</span>
                     </td>
                   </tr>
                   {/* Row 3 */}
                   <tr className="border-b border-outline-variant/30 hover:bg-[#1e293b]/30 cursor-pointer transition-colors">
                     <td className="p-4 pl-6 text-outline">Oct 24, 14:05:02</td>
                     <td className="p-4 text-[#45e0a0] font-bold flex items-center gap-1"><div className="w-1.5 h-1.5 rounded-full bg-[#45e0a0]/30 border border-[#45e0a0]" /> #VSH-9372</td>
                     <td className="p-4">
                       <div className="flex flex-col">
                         <span className="text-on-surface font-bold">+1 (415) 800-2911</span>
                         <span className="text-outline text-[9px] mt-0.5">US Landline (San Francisco)</span>
                       </div>
                     </td>
                     <td className="p-4 text-on-surface font-bold">CFO Executive</td>
                     <td className="p-4 text-outline">01:05</td>
                     <td className="p-4">
                       <span className="px-2 py-1 bg-[#45e0a0]/20 text-[#45e0a0] rounded text-[10px] font-bold border border-[#45e0a0]/30">12 L</span>
                     </td>
                   </tr>
                   {/* Row 4 */}
                   <tr className="border-b border-outline-variant/30 hover:bg-[#1e293b]/30 cursor-pointer transition-colors">
                     <td className="p-4 pl-6 text-outline">Oct 24, 13:49:50</td>
                     <td className="p-4 text-[#00c8e8] font-bold flex items-center gap-1"><div className="w-1.5 h-1.5 rounded-full bg-[#00c8e8]" /> #VSH-9365</td>
                     <td className="p-4">
                       <div className="flex flex-col">
                         <span className="text-on-surface font-bold">+33 1 42 68 55 08</span>
                         <span className="text-outline text-[9px] mt-0.5">France SIP Peer (Orange)</span>
                       </div>
                     </td>
                     <td className="p-4 text-on-surface font-bold">Wire Operations</td>
                     <td className="p-4 text-outline">03:45</td>
                     <td className="p-4">
                       <span className="px-2 py-1 bg-error/20 text-error rounded text-[10px] font-bold border border-error/30">91 C</span>
                     </td>
                   </tr>
                   {/* Row 5 */}
                   <tr className="border-b border-outline-variant/30 hover:bg-[#1e293b]/30 cursor-pointer transition-colors">
                     <td className="p-4 pl-6 text-outline">Oct 24, 13:30:11</td>
                     <td className="p-4 text-[#45e0a0] font-bold flex items-center gap-1"><div className="w-1.5 h-1.5 rounded-full bg-[#45e0a0]/30 border border-[#45e0a0]" /> #VSH-9351</td>
                     <td className="p-4">
                       <div className="flex flex-col">
                         <span className="text-on-surface font-bold">+1 (202) 555-0143</span>
                         <span className="text-outline text-[9px] mt-0.5">US Fixed PSTN (DC)</span>
                       </div>
                     </td>
                     <td className="p-4 text-on-surface font-bold">Customer Support Tier 2</td>
                     <td className="p-4 text-outline">05:20</td>
                     <td className="p-4">
                       <span className="px-2 py-1 bg-[#45e0a0]/20 text-[#45e0a0] rounded text-[10px] font-bold border border-[#45e0a0]/30">18 L</span>
                     </td>
                   </tr>
                   {/* Row 6 */}
                   <tr className="border-b border-outline-variant/30 hover:bg-[#1e293b]/30 cursor-pointer transition-colors">
                     <td className="p-4 pl-6 text-outline">Oct 24, 13:12:00</td>
                     <td className="p-4 text-[#00c8e8] font-bold flex items-center gap-1"><div className="w-1.5 h-1.5 rounded-full bg-[#00c8e8]" /> #VSH-9340</td>
                     <td className="p-4">
                       <div className="flex flex-col">
                         <span className="text-on-surface font-bold">+61 2 9374 4000</span>
                         <span className="text-outline text-[9px] mt-0.5">Australia Transit</span>
                       </div>
                     </td>
                     <td className="p-4 text-on-surface font-bold">SecOps Incident Desk</td>
                     <td className="p-4 text-outline">01:54</td>
                     <td className="p-4">
                       <span className="px-2 py-1 bg-[#facc15]/20 text-[#facc15] rounded text-[10px] font-bold border border-[#facc15]/30">60 M</span>
                     </td>
                   </tr>
                 </tbody>
               </table>
            </div>
         </div>

         {/* Side Panel */}
         <div className="w-96 bg-[#0f172a] border border-outline-variant rounded-lg shadow-xl flex flex-col shrink-0">
            {/* Panel Header */}
            <div className="flex justify-between items-start p-4 border-b border-outline-variant/50 bg-[#1e293b]/20">
               <div className="flex items-start gap-2">
                 <div className="p-1.5 bg-[#00c8e8]/20 border border-[#00c8e8]/40 rounded mt-0.5"><TableIcon className="w-3.5 h-3.5 text-[#00c8e8]"/></div>
                 <div className="flex flex-col">
                    <h3 className="font-headline-sm text-[15px] font-semibold text-on-surface">Call Inspection #VSH-9402</h3>
                    <span className="font-body-sm text-[11px] text-outline">Real-Time Ingress Forensics</span>
                 </div>
               </div>
               <button className="p-1 text-outline hover:text-on-surface transition-colors"><X className="w-4 h-4"/></button>
            </div>

            <div className="p-5 flex flex-col gap-6 overflow-auto">
               <div className="flex justify-between items-center border-b border-outline-variant/50 pb-3">
                 <div className="flex items-center gap-2 font-label-sm text-[10px] font-bold uppercase tracking-widest text-error">
                   <div className="w-2 h-2 rounded-full bg-error" /> UNVERIFIED - HIGH THREAT
                 </div>
                 <span className="font-code-sm text-[11px] text-error font-bold">98.6% Synthetic</span>
               </div>

               {/* Waveform Player */}
               <div className="flex flex-col gap-2">
                 <div className="flex justify-between items-center font-label-sm text-[9px] text-outline uppercase tracking-widest font-bold">
                   <span>ACOUSTIC AUDIO STREAM CAPTURE</span>
                   <span className="text-[#00c8e8] font-code-sm">01:14 / 02:30</span>
                 </div>
                 <div className="h-20 w-full bg-[#1e293b] border border-outline-variant rounded flex items-center justify-center p-2 relative">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={mockWaveformData}>
                        <Area type="step" dataKey="val" stroke="#00c8e8" fill="transparent" strokeWidth={1.5} isAnimationActive={false}/>
                      </AreaChart>
                    </ResponsiveContainer>
                    <div className="absolute left-1/2 top-0 bottom-0 w-px bg-error z-10" />
                 </div>
                 <div className="flex justify-between items-center mt-1">
                   <div className="flex gap-2">
                     <button className="p-1.5 bg-[#00c8e8] text-[#0f172a] rounded"><Pause className="w-3.5 h-3.5 fill-current"/></button>
                     <button className="p-1.5 text-outline hover:text-on-surface border border-outline-variant rounded"><RotateCcw className="w-3.5 h-3.5"/></button>
                   </div>
                   <span className="font-code-sm text-[9px] text-outline flex items-center gap-1"><AlertTriangle className="w-3 h-3"/> FLAC 24-bit / 48kHz</span>
                 </div>
               </div>

               {/* Engine Verdict */}
               <div className="flex flex-col gap-2 border-b border-outline-variant/50 pb-4">
                 <div className="flex justify-between font-label-sm text-[9px] uppercase tracking-widest font-bold">
                   <span className="text-outline">ENGINE VERDICT</span>
                   <span className="text-error bg-error/10 px-1 rounded">Model V4.2</span>
                 </div>
                 <p className="font-body-sm text-[12px] text-error font-semibold leading-relaxed">
                   ElevenLabs clone signature detected on CFO voice profile. <span className="text-[#00c8e8]">Latency jitter: 4ms, synthetic breathing artifact at timestamp 00:48.21.</span>
                 </p>
               </div>

               {/* Enrollment Comparison */}
               <div className="flex flex-col gap-3 border-b border-outline-variant/50 pb-4">
                 <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest font-bold mb-1">ENROLLMENT COMPARISON</span>
                 <div className="flex justify-between items-center">
                   <span className="font-label-sm text-[10px] text-outline">Target Identity</span>
                   <span className="font-label-sm text-[11px] text-on-surface font-bold">David Vance (Exec CFO)</span>
                 </div>
                 <div className="flex justify-between items-center">
                   <span className="font-label-sm text-[10px] text-outline">Vocal Formant Correlation</span>
                   <span className="font-label-sm text-[11px] text-error font-bold">12.4% (Mismatch)</span>
                 </div>
                 <div className="flex justify-between items-center">
                   <span className="font-label-sm text-[10px] text-outline">Carrier Spoofing Check</span>
                   <span className="font-label-sm text-[11px] text-[#facc15] font-bold">VoIP Provider / High Discrepancy</span>
                 </div>
                 <div className="flex justify-between items-center">
                   <span className="font-label-sm text-[10px] text-outline">Session Intercept Route</span>
                   <span className="font-label-sm text-[11px] text-[#00c8e8] font-bold">Auto-Diverted to SOC Honeynet</span>
                 </div>
               </div>

               {/* Analyst Log */}
               <div className="flex flex-col gap-2">
                 <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest font-bold mb-1">ANALYST TRIAGE LOG</span>
                 <textarea 
                   className="w-full bg-[#1e293b] border border-outline-variant rounded p-3 text-[11px] font-body-sm text-on-surface min-h-[60px] focus:outline-none focus:border-[#00c8e8]"
                   placeholder="Add cryptographic notes or forensic tags..."
                 />
               </div>

               <div className="flex flex-col gap-3 mt-4">
                 <button className="w-full py-2.5 bg-[#00c8e8] hover:bg-[#00c8e8]/90 text-[#0f172a] rounded font-label-sm text-[11px] uppercase tracking-wider font-bold transition-colors flex justify-center items-center gap-2">
                   Open Full Investigation
                 </button>
                 <button className="w-full py-2.5 border border-error/50 hover:bg-error/10 text-error rounded font-label-sm text-[11px] uppercase tracking-wider font-bold transition-colors">
                   Add Caller to Blocklist
                 </button>
               </div>
            </div>
         </div>
      </div>
    </div>
  );
};

export default CallHistory;
