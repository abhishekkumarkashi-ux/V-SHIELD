import { Shield, Activity, Percent, Zap, Info, Target, Download, Filter, CheckCircle2 } from 'lucide-react';
import { LineChart, Line, XAxis, ResponsiveContainer, Tooltip } from 'recharts';

const trendData = [
  { date: 'Oct 18', high: 15, med: 30, low: 25 },
  { date: 'Oct 19', high: 20, med: 25, low: 20 },
  { date: 'Oct 20', high: 18, med: 35, low: 30 },
  { date: 'Oct 21', high: 22, med: 40, low: 25 },
  { date: 'Oct 22', high: 25, med: 30, low: 20 },
  { date: 'Oct 23', high: 38, med: 50, low: 35 },
  { date: 'Oct 24', high: 28, med: 40, low: 30 },
];

const RiskIntelligence = () => {
  return (
    <div className="flex flex-col w-full h-full gap-4">
      {/* Header Section */}
      <div className="flex flex-col gap-4 border-b border-outline-variant/50 pb-5">
        <div className="flex justify-between items-start">
          <div className="flex flex-col gap-1">
            <span className="font-code-sm text-[10px] text-[#00c8e8] tracking-widest uppercase font-bold flex items-center gap-1">
              TELEMETRIC INTELLIGENCE UNIT - <span className="text-[#45e0a0]">CLUSTER US-EAST-01 ACTIVE</span>
            </span>
            <h1 className="font-headline-xl text-3xl text-on-surface tracking-tight font-semibold mt-1">Risk Intelligence</h1>
            <p className="font-body-sm text-sm text-outline mt-1">Global voice threat telemetry, synthetic voice vectors, and anomaly distributions.</p>
          </div>
          <div className="flex flex-col gap-3 items-end">
            <div className="flex items-center bg-[#0f172a] rounded border border-outline-variant">
              <button className="px-4 py-1.5 font-label-sm text-[11px] text-outline hover:text-on-surface transition-colors">Today</button>
              <button className="px-4 py-1.5 font-label-sm text-[11px] bg-[#00c8e8]/20 text-[#00c8e8] border-x border-outline-variant font-bold">7 Days</button>
              <button className="px-4 py-1.5 font-label-sm text-[11px] text-outline hover:text-on-surface transition-colors border-r border-outline-variant">30 Days</button>
              <button className="px-4 py-1.5 font-label-sm text-[11px] text-outline hover:text-on-surface transition-colors border-r border-outline-variant">90 Days</button>
              <button className="px-4 py-1.5 font-label-sm text-[11px] text-outline hover:text-on-surface transition-colors">Custom Range</button>
            </div>
            <div className="flex items-center gap-3">
              <button className="flex items-center gap-2 px-3 py-1.5 rounded bg-surface-container border border-outline-variant text-xs text-on-surface hover:bg-surface-container-high transition-colors font-bold">
                <Filter className="w-3.5 h-3.5" /> Severity: All Vectors <span className="opacity-50 ml-1">▼</span>
              </button>
              <button className="flex items-center gap-2 px-3 py-1.5 rounded border border-[#00c8e8]/50 text-[#00c8e8] hover:bg-[#00c8e8]/10 transition-colors font-label-sm text-xs font-bold uppercase tracking-wider">
                <Download className="w-3.5 h-3.5" /> Export CSV
              </button>
            </div>
          </div>
        </div>

        {/* 4 Metrics */}
        <div className="grid grid-cols-4 gap-4 mt-2">
          {/* Card 1 */}
          <div className="bg-[#0f172a] border border-outline-variant rounded p-4 flex flex-col justify-between shadow-lg h-28 relative">
            <div className="flex justify-between items-start">
              <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest font-bold">MEAN IMPERSONATION RISK</span>
              <Shield className="w-4 h-4 text-[#00c8e8]" />
            </div>
            <div className="flex flex-col">
              <div className="flex items-baseline gap-1 mt-1">
                <span className="text-[2.5rem] font-headline-sm font-bold tracking-tight text-on-surface leading-none">24.2</span>
                <span className="text-xs font-label-sm text-outline font-bold">/ 100</span>
              </div>
              <div className="flex items-center gap-2 mt-2">
                <span className="font-label-sm text-[10px] text-[#45e0a0] font-bold flex items-center gap-1">↘ -3.1%</span>
                <span className="font-label-sm text-[10px] text-outline">vs prior 7-day baseline</span>
              </div>
            </div>
          </div>
          {/* Card 2 */}
          <div className="bg-[#0f172a] border border-outline-variant rounded p-4 flex flex-col justify-between shadow-lg h-28 relative">
            <div className="flex justify-between items-start">
              <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest font-bold">DETECTED SYNTHETIC VECTORS</span>
              <Activity className="w-4 h-4 text-[#ffaaa0]" />
            </div>
            <div className="flex flex-col">
              <div className="flex items-baseline gap-1 mt-1">
                <span className="text-[2.5rem] font-headline-sm font-bold tracking-tight text-on-surface leading-none">142</span>
                <span className="text-xs font-label-sm text-outline font-bold">Total</span>
              </div>
              <div className="flex items-center gap-2 mt-2">
                <span className="font-label-sm text-[10px] text-[#ffaaa0] font-bold">9 Active Waves</span>
                <span className="font-label-sm text-[10px] text-outline">across PSTN carriers</span>
              </div>
            </div>
          </div>
          {/* Card 3 */}
          <div className="bg-[#0f172a] border border-outline-variant rounded p-4 flex flex-col justify-between shadow-lg h-28 relative">
            <div className="flex justify-between items-start">
              <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest font-bold">ATTEMPT RATE</span>
              <Percent className="w-4 h-4 text-outline" />
            </div>
            <div className="flex flex-col">
              <div className="flex items-baseline gap-1 mt-1">
                <span className="text-[2.5rem] font-headline-sm font-bold tracking-tight text-on-surface leading-none">0.38%</span>
                <span className="text-xs font-label-sm text-outline font-bold">of total calls</span>
              </div>
              <div className="flex items-center gap-2 mt-2">
                <span className="font-code-sm text-[10px] text-on-surface font-bold">37,420</span>
                <span className="font-label-sm text-[10px] text-outline">inspected voice frames</span>
              </div>
            </div>
          </div>
          {/* Card 4 */}
          <div className="bg-[#0f172a] border border-outline-variant rounded p-4 flex flex-col justify-between shadow-lg h-28 relative">
            <div className="flex justify-between items-start">
              <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest font-bold">MITIGATION SLA</span>
              <Zap className="w-4 h-4 text-[#45e0a0]" />
            </div>
            <div className="flex flex-col">
              <div className="flex items-baseline gap-1 mt-1">
                <span className="text-[2.5rem] font-headline-sm font-bold tracking-tight text-[#45e0a0] leading-none">1.4s</span>
                <span className="text-xs font-label-sm text-outline font-bold">avg response</span>
              </div>
              <div className="flex items-center gap-2 mt-2">
                <CheckCircle2 className="w-3 h-3 text-[#45e0a0]" />
                <span className="font-label-sm text-[10px] text-[#45e0a0] font-bold">320ms</span>
                <span className="font-label-sm text-[10px] text-outline">model inference budget</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5 mt-2">
        {/* Left Column: Line Chart & Risk Distribution */}
        <div className="flex flex-col gap-5">
          <div className="bg-[#0f172a] border border-outline-variant rounded p-6 shadow-lg flex flex-col gap-4">
            <div className="flex justify-between items-start mb-2">
              <div className="flex flex-col">
                <h3 className="font-headline-sm text-lg text-on-surface font-semibold">Risk Score & Impersonation Trend</h3>
                <span className="font-body-sm text-xs text-outline mt-1 tracking-wide">Seven-day trajectory across low, medium, and high telemetry tiers.</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-1.5"><div className="w-2 h-2 rounded-full bg-[#ffaaa0]" /><span className="text-[10px] text-outline font-bold">High</span></div>
                <div className="flex items-center gap-1.5"><div className="w-2 h-2 rounded-full bg-[#a78bfa]" /><span className="text-[10px] text-outline font-bold">Med</span></div>
                <div className="flex items-center gap-1.5"><div className="w-2 h-2 rounded-full bg-[#45e0a0]" /><span className="text-[10px] text-outline font-bold">Low</span></div>
              </div>
            </div>

            <div className="h-48 w-full relative -ml-4">
              <ResponsiveContainer width="100%" height="100%">
                 <LineChart data={trendData} margin={{ top: 20, right: 0, left: 0, bottom: 0 }}>
                   <XAxis dataKey="date" axisLine={{stroke: '#334155'}} tickLine={false} tick={{ fill: '#64748b', fontSize: 10, fontFamily: 'JetBrains Mono' }} dy={10} />
                   <Tooltip contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155', borderRadius: '4px', fontSize: '10px' }} />
                   <Line type="linear" dataKey="high" stroke="#ffaaa0" strokeWidth={2} dot={{r:3, fill:'#ffaaa0', strokeWidth:0}} activeDot={{ r: 5 }} />
                   <Line type="linear" dataKey="med" stroke="#a78bfa" strokeWidth={2} dot={false} />
                   <Line type="linear" dataKey="low" stroke="#45e0a0" strokeWidth={2} dot={false} />
                 </LineChart>
              </ResponsiveContainer>
              {/* Tooltip Overlay Mock for Peak */}
              <div className="absolute top-2 left-1/2 bg-[#1e293b] border border-outline-variant px-3 py-2 rounded text-center shadow-xl">
                 <span className="font-label-sm text-[10px] text-outline block">Oct 23 (Peak Incident)</span>
                 <span className="font-label-sm text-[11px] text-[#ffaaa0] font-bold block mt-0.5">High: 38 Vectors <span className="text-outline font-normal">| Latency: 1.1s</span></span>
              </div>
            </div>

            <div className="mt-4 bg-[#00c8e8]/10 border border-[#00c8e8]/30 rounded p-3 flex justify-between items-center">
               <div className="flex items-center gap-2">
                 <div className="p-1 rounded-full bg-[#00c8e8]/20"><Activity className="w-4 h-4 text-[#00c8e8]" /></div>
                 <span className="font-body-sm text-[11px] text-[#00c8e8] font-bold">Algorithmic Correlation: Synthesis bursts match overseas VoIP routing</span>
               </div>
               <span className="font-code-sm text-[11px] text-[#00c8e8] font-bold">p &lt; 0.001</span>
            </div>
          </div>

          <div className="bg-[#0f172a] border border-outline-variant rounded p-6 shadow-lg flex flex-col gap-4">
             <div className="flex justify-between items-start mb-2">
               <div className="flex flex-col">
                 <h3 className="font-headline-sm text-lg text-on-surface font-semibold">Enterprise Risk Distribution</h3>
                 <span className="font-body-sm text-xs text-outline mt-1 tracking-wide">Acoustic biometric population risk stratifications</span>
               </div>
               <span className="font-code-sm text-[10px] text-outline uppercase tracking-widest">N = 37,420 STREAMS</span>
             </div>
             
             {/* Progress Bar */}
             <div className="h-3 w-full bg-surface-container-highest rounded-full overflow-hidden flex my-2">
               <div className="h-full bg-[#45e0a0]" style={{ width: '91.2%' }}></div>
               <div className="h-full bg-[#a78bfa]" style={{ width: '6.8%' }}></div>
               <div className="h-full bg-[#00c8e8]" style={{ width: '1.5%' }}></div>
               <div className="h-full bg-[#ffaaa0]" style={{ width: '0.5%' }}></div>
             </div>
             
             {/* Legend */}
             <div className="grid grid-cols-4 gap-2 mt-2">
               <div className="flex flex-col">
                 <div className="flex items-center gap-1.5">
                   <div className="w-1.5 h-1.5 rounded-full bg-[#45e0a0]" />
                   <span className="font-label-sm text-[10px] text-outline">Low Risk (&lt;25)</span>
                 </div>
                 <span className="font-headline-sm text-xl text-[#45e0a0] font-bold mt-1">91.2%</span>
                 <span className="font-label-sm text-[9px] text-outline mt-0.5">34,127 calls</span>
               </div>
               <div className="flex flex-col">
                 <div className="flex items-center gap-1.5">
                   <div className="w-1.5 h-1.5 rounded-full bg-[#a78bfa]" />
                   <span className="font-label-sm text-[10px] text-outline">Moderate (26-60)</span>
                 </div>
                 <span className="font-headline-sm text-xl text-on-surface font-bold mt-1">6.8%</span>
                 <span className="font-label-sm text-[9px] text-outline mt-0.5">2,544 calls</span>
               </div>
               <div className="flex flex-col">
                 <div className="flex items-center gap-1.5">
                   <div className="w-1.5 h-1.5 rounded-full bg-[#00c8e8]" />
                   <span className="font-label-sm text-[10px] text-outline">High (61-80)</span>
                 </div>
                 <span className="font-headline-sm text-xl text-on-surface font-bold mt-1">1.5%</span>
                 <span className="font-label-sm text-[9px] text-outline mt-0.5">562 calls</span>
               </div>
               <div className="flex flex-col">
                 <div className="flex items-center gap-1.5">
                   <div className="w-1.5 h-1.5 rounded-full bg-[#ffaaa0]" />
                   <span className="font-label-sm text-[10px] text-outline">Critical (&gt;80)</span>
                 </div>
                 <span className="font-headline-sm text-xl text-[#ffaaa0] font-bold mt-1">0.5%</span>
                 <span className="font-label-sm text-[9px] text-outline mt-0.5">187 calls</span>
               </div>
             </div>
          </div>
        </div>

        {/* Right Column: Categories & Top Indicators */}
        <div className="flex flex-col gap-5">
          <div className="bg-[#0f172a] border border-outline-variant rounded p-6 shadow-lg flex flex-col gap-6">
             <div className="flex justify-between items-start">
               <div className="flex flex-col">
                 <h3 className="font-headline-sm text-lg text-on-surface font-semibold">Threat Detection by Category</h3>
                 <span className="font-body-sm text-xs text-outline mt-1 tracking-wide leading-tight">Classified architecture distribution of flagged impersonation<br/>attempts</span>
               </div>
               <div className="flex flex-col items-end">
                 <span className="font-headline-sm text-xl text-[#00c8e8] font-bold">142</span>
                 <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest font-bold">TOTAL</span>
               </div>
             </div>
             
             <div className="flex flex-col gap-4">
               {/* Item 1 */}
               <div className="flex flex-col gap-1">
                 <div className="flex justify-between items-center mb-1">
                   <div className="flex items-center gap-2">
                     <div className="w-2 h-2 rounded-full bg-[#00c8e8]" />
                     <span className="font-label-sm text-xs text-on-surface">Voice Cloning <span className="text-outline font-normal">(ElevenLabs / Tortoise)</span></span>
                   </div>
                   <span className="font-code-sm text-[11px] text-outline">68 hits <span className="text-[#00c8e8] font-bold">48%</span></span>
                 </div>
                 <div className="h-1.5 w-full bg-surface-container-highest rounded-r overflow-hidden"><div className="h-full bg-[#00c8e8]" style={{width: '48%'}}/></div>
               </div>
               {/* Item 2 */}
               <div className="flex flex-col gap-1">
                 <div className="flex justify-between items-center mb-1">
                   <div className="flex items-center gap-2">
                     <div className="w-2 h-2 rounded-full bg-[#ffaaa0]" />
                     <span className="font-label-sm text-xs text-on-surface">Speaker Mismatch <span className="text-outline font-normal">(Impersonation)</span></span>
                   </div>
                   <span className="font-code-sm text-[11px] text-outline">37 hits <span className="text-[#ffaaa0] font-bold">26%</span></span>
                 </div>
                 <div className="h-1.5 w-full bg-surface-container-highest rounded-r overflow-hidden"><div className="h-full bg-[#ffaaa0]" style={{width: '26%'}}/></div>
               </div>
               {/* Item 3 */}
               <div className="flex flex-col gap-1">
                 <div className="flex justify-between items-center mb-1">
                   <div className="flex items-center gap-2">
                     <div className="w-2 h-2 rounded-full bg-[#a78bfa]" />
                     <span className="font-label-sm text-xs text-on-surface">Audio Replay / Injection</span>
                   </div>
                   <span className="font-code-sm text-[11px] text-outline">23 hits <span className="text-[#a78bfa] font-bold">16%</span></span>
                 </div>
                 <div className="h-1.5 w-full bg-surface-container-highest rounded-r overflow-hidden"><div className="h-full bg-[#a78bfa]" style={{width: '16%'}}/></div>
               </div>
               {/* Item 4 */}
               <div className="flex flex-col gap-1">
                 <div className="flex justify-between items-center mb-1">
                   <div className="flex items-center gap-2">
                     <div className="w-2 h-2 rounded-full bg-[#45e0a0]" />
                     <span className="font-label-sm text-xs text-on-surface">Conversational AI Bots</span>
                   </div>
                   <span className="font-code-sm text-[11px] text-outline">14 hits <span className="text-[#45e0a0] font-bold">10%</span></span>
                 </div>
                 <div className="h-1.5 w-full bg-surface-container-highest rounded-r overflow-hidden"><div className="h-full bg-[#45e0a0]" style={{width: '10%'}}/></div>
               </div>
             </div>

             <div className="mt-2 border-t border-outline-variant/30 pt-4 flex justify-between items-center">
               <div className="flex items-center gap-2 max-w-[75%]">
                 <Info className="w-4 h-4 text-outline shrink-0" />
                 <span className="font-body-sm text-[11px] text-outline leading-tight">Zero-shot neural speech synthesis models comprise over 74% of target encounters.</span>
               </div>
               <button className="px-3 py-1.5 border border-outline-variant rounded font-label-sm text-[10px] uppercase font-bold tracking-wider hover:bg-surface-container-high transition-colors">
                 Inspect Signatures
               </button>
             </div>
          </div>

          <div className="bg-[#0f172a] border border-outline-variant rounded p-6 shadow-lg flex flex-col gap-4">
             <div className="flex justify-between items-start mb-2">
               <div className="flex flex-col">
                 <h3 className="font-headline-sm text-lg text-on-surface font-semibold">Top Threat Indicators & Attack Patterns</h3>
                 <span className="font-body-sm text-xs text-outline mt-1 tracking-wide">Primary synthetic voice artifacts mapped from live quarantine logs</span>
               </div>
               <Target className="w-5 h-5 text-[#00c8e8]" />
             </div>
             
             <div className="flex flex-col gap-3">
               <div className="flex items-start gap-4 p-3 bg-surface-container-lowest border border-outline-variant rounded">
                 <div className="w-6 h-6 rounded bg-surface-container-highest flex items-center justify-center font-code-md text-xs font-bold text-outline">1</div>
                 <div className="flex flex-col gap-1 flex-1">
                   <span className="font-label-sm text-sm text-[#00c8e8] font-bold">High-frequency phase incongruity</span>
                   <span className="font-body-sm text-[11px] text-outline">Synthetic vocoder spectral glottal pulse mismatches</span>
                 </div>
                 <div className="flex items-baseline gap-1">
                   <span className="font-headline-sm text-lg text-on-surface font-bold">44.2%</span>
                   <span className="font-label-sm text-[9px] text-outline uppercase">of flagged</span>
                 </div>
               </div>

               <div className="flex items-start gap-4 p-3 bg-surface-container-lowest border border-outline-variant rounded">
                 <div className="w-6 h-6 rounded bg-surface-container-highest flex items-center justify-center font-code-md text-xs font-bold text-outline">2</div>
                 <div className="flex flex-col gap-1 flex-1">
                   <span className="font-label-sm text-sm text-[#00c8e8] font-bold truncate">Known spoofed telecom carrier ANI origi...</span>
                   <span className="font-body-sm text-[11px] text-outline">STIR/SHAKEN Attestation C with unverified SS7 trunking</span>
                 </div>
                 <div className="flex items-baseline gap-1">
                   <span className="font-headline-sm text-lg text-on-surface font-bold">28.6%</span>
                   <span className="font-label-sm text-[9px] text-outline uppercase">of flagged</span>
                 </div>
               </div>
             </div>
          </div>
        </div>

      </div>
    </div>
  );
};

export default RiskIntelligence;
