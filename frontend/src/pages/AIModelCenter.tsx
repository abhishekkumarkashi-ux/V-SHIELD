import { RefreshCw, Rocket, Network, Timer, CheckCircle, Activity, LayoutGrid, Fingerprint, SlidersHorizontal, ArrowRight } from 'lucide-react';
import { BarChart, Bar, Cell, ResponsiveContainer, LineChart, Line } from 'recharts';

const mockBarData = [
  { val: 20 }, { val: 40 }, { val: 30 }, { val: 60 }, { val: 50 }, 
  { val: 80 }, { val: 40 }, { val: 70 }, { val: 35 }, { val: 25 }
];

const mockLineData = [
  { val: 10, error: 0 }, { val: 15, error: 0 }, { val: 12, error: 0 },
  { val: 40, error: 40 }, { val: 20, error: 0 }, { val: 25, error: 0 },
  { val: 18, error: 0 }
];

const AIModelCenter = () => {
  return (
    <div className="flex flex-col w-full h-full gap-4 pb-10">
      {/* Header Section */}
      <div className="flex flex-col gap-4 border-b border-outline-variant/50 pb-5">
        <div className="flex justify-between items-start">
          <div className="flex flex-col gap-1">
            <span className="font-code-sm text-[10px] text-primary tracking-widest uppercase font-bold flex items-center gap-1">
              NEURAL GOVERNANCE & INFERENCE TELEMETRY
            </span>
            <h1 className="font-headline-xl text-3xl text-on-surface tracking-tight font-semibold mt-1">AI Model Center</h1>
            <p className="font-body-sm text-sm text-outline mt-1">Inspect, benchmark, and deploy deep learning models powering real-time voice verification.</p>
          </div>
          <div className="flex items-center gap-3 mt-1">
            <button className="flex items-center gap-2 px-5 py-2.5 border border-outline-variant text-on-surface hover:bg-surface-container-high transition-colors rounded font-label-sm text-[11px] uppercase tracking-wider font-bold">
              <RefreshCw className="w-4 h-4" /> Run Benchmark Suite
            </button>
            <button className="flex items-center gap-2 px-5 py-2.5 bg-[#00c8e8] text-[#0f172a] hover:bg-[#00c8e8]/90 transition-colors rounded font-label-sm text-[11px] uppercase tracking-wider font-bold">
              <Rocket className="w-4 h-4 fill-current" /> Deploy Model Update
            </button>
          </div>
        </div>

        {/* 4 KPIs */}
        <div className="grid grid-cols-4 gap-4 mt-2">
          {/* Card 1 */}
          <div className="bg-[#0f172a] border border-outline-variant rounded p-4 flex flex-col justify-between shadow-lg h-28 relative">
            <div className="flex justify-between items-start">
              <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest font-bold">DEPLOYED MODELS</span>
              <Network className="w-4 h-4 text-[#00c8e8]" />
            </div>
            <div className="flex items-baseline gap-1 mt-1">
              <span className="text-[2.5rem] font-headline-sm font-bold tracking-tight text-on-surface leading-none">4</span>
              <span className="text-xs font-label-sm text-[#45e0a0] font-bold">Active</span>
            </div>
            <div className="flex flex-col mt-2">
               <span className="font-label-sm text-[10px] text-outline">Dual-edge pipeline redundancy</span>
               <span className="font-label-sm text-[10px] text-[#45e0a0] font-bold flex items-center gap-1 mt-0.5">
                 <div className="w-1.5 h-1.5 rounded-full bg-[#45e0a0]" /> 100% Core Availability
               </span>
            </div>
          </div>
          
          {/* Card 2 */}
          <div className="bg-[#0f172a] border border-outline-variant rounded p-4 flex flex-col justify-between shadow-lg h-28 relative">
            <div className="flex justify-between items-start">
              <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest font-bold">AVG REAL-TIME LATENCY</span>
              <Timer className="w-4 h-4 text-[#45e0a0]" />
            </div>
            <div className="flex items-baseline gap-1 mt-1">
              <span className="text-[2.5rem] font-headline-sm font-bold tracking-tight text-on-surface leading-none">21.4</span>
              <span className="text-xs font-label-sm text-outline font-bold">ms</span>
            </div>
            <div className="flex flex-col mt-2">
               <span className="font-label-sm text-[10px] text-outline mb-1">Target &lt; 35ms SLA</span>
               <div className="w-full h-1 bg-surface-container-highest rounded">
                 <div className="h-full bg-[#45e0a0] rounded" style={{width: '60%'}}></div>
               </div>
            </div>
          </div>

          {/* Card 3 */}
          <div className="bg-[#0f172a] border border-outline-variant rounded p-4 flex flex-col justify-between shadow-lg h-28 relative">
            <div className="flex justify-between items-start">
              <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest font-bold">MEAN MODEL ACCURACY</span>
              <CheckCircle className="w-4 h-4 text-outline" />
            </div>
            <div className="flex items-baseline gap-1 mt-1">
              <span className="text-[2.5rem] font-headline-sm font-bold tracking-tight text-on-surface leading-none">98.2</span>
              <span className="text-xs font-label-sm text-outline font-bold">%</span>
            </div>
            <div className="flex flex-col mt-2">
               <span className="font-label-sm text-[10px] text-outline">Across composite evaluation suite</span>
               <span className="font-label-sm text-[10px] text-[#45e0a0] font-bold mt-0.5">↑ +0.4% from v4.1 checkpoint</span>
            </div>
          </div>

          {/* Card 4 */}
          <div className="bg-[#0f172a] border border-outline-variant rounded p-4 flex flex-col justify-between shadow-lg h-28 relative">
            <div className="flex justify-between items-start">
              <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest font-bold">TOTAL INFERENCES TODAY</span>
              <Activity className="w-4 h-4 text-[#00c8e8]" />
            </div>
            <div className="flex items-baseline gap-1 mt-1">
              <span className="text-[2.5rem] font-headline-sm font-bold tracking-tight text-on-surface leading-none">184,290</span>
            </div>
            <div className="flex flex-col mt-2">
               <span className="font-label-sm text-[10px] text-outline">Audio segments verified</span>
               <span className="font-label-sm text-[10px] text-outline mt-0.5">Peak: <span className="text-on-surface font-bold">4.8k ops/sec</span> <span className="text-[#00c8e8] font-bold">0 Dropouts</span></span>
            </div>
          </div>
        </div>
      </div>

      {/* Model Inventory */}
      <div className="flex flex-col gap-4">
         <div className="flex justify-between items-center px-1">
            <h3 className="font-headline-sm text-[15px] font-semibold text-on-surface flex items-center gap-2">
              <LayoutGrid className="w-4 h-4 text-[#00c8e8]" /> Core Telemetry & Model Inventory
            </h3>
            <span className="font-code-sm text-[10px] text-outline uppercase tracking-widest">ENGINE SYNC STATUS: <span className="text-on-surface font-bold">REALTIME</span></span>
         </div>

         <div className="grid grid-cols-2 gap-5">
            {/* Model Card 1 */}
            <div className="bg-[#0f172a] border border-outline-variant rounded-lg p-5 shadow flex flex-col justify-between min-h-[220px]">
               <div className="flex flex-col gap-1">
                  <div className="flex justify-between items-center mb-1">
                     <div className="flex items-center gap-2">
                        <span className="px-1.5 py-0.5 bg-[#45e0a0]/10 text-[#45e0a0] rounded font-label-sm text-[9px] uppercase font-bold tracking-widest flex items-center gap-1">
                          <div className="w-1.5 h-1.5 rounded-full bg-[#45e0a0]" /> ACTIVE
                        </span>
                        <span className="px-1.5 py-0.5 bg-surface-container border border-outline-variant rounded font-code-sm text-[10px] text-outline">v4.2.1-prod</span>
                     </div>
                     <span className="font-code-sm text-[10px] text-outline">UUID: <span className="text-on-surface font-bold">tf-8802a</span></span>
                  </div>
                  <h3 className="font-headline-sm text-lg font-bold text-on-surface mt-2">V-SHIELD Anti-Spoofing Transformer v4.2</h3>
                  <span className="font-body-sm text-[12px] text-outline">Synthetic Voice & Vocoder Artifact Detection</span>
               </div>
               
               <div className="mt-4 flex flex-col gap-2">
                  <div className="flex justify-between font-label-sm text-[9px] uppercase tracking-widest font-bold">
                    <span className="text-outline">SPECTRAL ARTIFACT PROBING</span>
                    <span className="text-[#45e0a0]">Zero-shot Generalization: HIGH</span>
                  </div>
                  <div className="h-10 w-full relative border-b border-outline-variant/30">
                     <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={mockBarData}>
                          <Bar dataKey="val">
                            {mockBarData.map((_, index) => (
                              <Cell key={`cell-${index}`} fill={index % 2 === 0 ? '#00c8e8' : '#ffaaa0'} fillOpacity={index % 2 === 0 ? 0.3 : 0.8} />
                            ))}
                          </Bar>
                        </BarChart>
                     </ResponsiveContainer>
                  </div>
                  
                  <div className="grid grid-cols-3 gap-2 mt-2">
                     <div className="flex flex-col">
                       <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest">ACCURACY</span>
                       <span className="font-code-sm text-[13px] text-on-surface font-bold">98.9%</span>
                     </div>
                     <div className="flex flex-col">
                       <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest">LATENCY</span>
                       <span className="font-code-sm text-[13px] text-[#00c8e8] font-bold">5.8ms</span>
                     </div>
                     <div className="flex flex-col">
                       <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest">ARCHITECTURE</span>
                       <span className="font-code-sm text-[11px] text-on-surface font-bold mt-0.5">Conformer + MSSA</span>
                     </div>
                  </div>
               </div>

               <div className="flex justify-between items-center border-t border-outline-variant/30 pt-4 mt-4">
                  <span className="font-label-sm text-[10px] text-outline">Updated 2 days ago</span>
                  <div className="flex items-center gap-4 font-label-sm text-[11px] font-bold">
                     <button className="text-outline hover:text-on-surface underline transition-colors">Retrain / Fine-tune</button>
                     <button className="flex items-center gap-1 text-[#00c8e8] hover:text-[#00c8e8]/80 transition-colors">View Telemetry <ArrowRight className="w-3 h-3"/></button>
                  </div>
               </div>
            </div>

            {/* Model Card 2 */}
            <div className="bg-[#0f172a] border border-outline-variant rounded-lg p-5 shadow flex flex-col justify-between min-h-[220px]">
               <div className="flex flex-col gap-1">
                  <div className="flex justify-between items-center mb-1">
                     <div className="flex items-center gap-2">
                        <span className="px-1.5 py-0.5 bg-[#45e0a0]/10 text-[#45e0a0] rounded font-label-sm text-[9px] uppercase font-bold tracking-widest flex items-center gap-1">
                          <div className="w-1.5 h-1.5 rounded-full bg-[#45e0a0]" /> ACTIVE
                        </span>
                        <span className="px-1.5 py-0.5 bg-surface-container border border-outline-variant rounded font-code-sm text-[10px] text-outline">v3.9.0-prod</span>
                     </div>
                     <span className="font-code-sm text-[10px] text-outline">UUID: <span className="text-on-surface font-bold">vp-1049b</span></span>
                  </div>
                  <h3 className="font-headline-sm text-lg font-bold text-on-surface mt-2">Biometric Speaker Verification Engine (VoicePrint)</h3>
                  <span className="font-body-sm text-[12px] text-outline">Deep Voice Embedding & Speaker Identification</span>
               </div>
               
               <div className="mt-4 flex flex-col gap-2">
                  <div className="flex items-center gap-4 p-2 bg-[#1e293b]/50 border border-outline-variant/50 rounded">
                     <div className="p-2 bg-surface-container-highest rounded"><Fingerprint className="w-6 h-6 text-[#a78bfa]"/></div>
                     <div className="flex flex-col flex-1">
                       <span className="font-headline-sm text-xl text-on-surface font-bold leading-none">4,820</span>
                       <span className="font-label-sm text-[10px] text-outline">Enrolled Verified Profiles</span>
                     </div>
                     <div className="flex flex-col items-end pr-2">
                       <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest font-bold">EER:</span>
                       <span className="font-code-sm text-[13px] text-[#45e0a0] font-bold">0.82%</span>
                     </div>
                  </div>
                  
                  <div className="grid grid-cols-3 gap-2 mt-2">
                     <div className="flex flex-col">
                       <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest">ACCURACY</span>
                       <span className="font-code-sm text-[13px] text-on-surface font-bold">97.4%</span>
                     </div>
                     <div className="flex flex-col">
                       <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest">LATENCY</span>
                       <span className="font-code-sm text-[13px] text-[#00c8e8] font-bold">4.6ms</span>
                     </div>
                     <div className="flex flex-col">
                       <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest">ARCHITECTURE</span>
                       <span className="font-code-sm text-[11px] text-on-surface font-bold mt-0.5">ResNet-34 AAM</span>
                     </div>
                  </div>
               </div>

               <div className="flex justify-between items-center border-t border-outline-variant/30 pt-4 mt-4">
                  <span className="font-label-sm text-[10px] text-outline">Updated 5 days ago</span>
                  <div className="flex items-center gap-4 font-label-sm text-[11px] font-bold">
                     <button className="text-outline hover:text-on-surface underline transition-colors">Benchmark</button>
                     <button className="flex items-center gap-1 text-[#00c8e8] hover:text-[#00c8e8]/80 transition-colors">Manage Embeddings <ArrowRight className="w-3 h-3"/></button>
                  </div>
               </div>
            </div>

            {/* Model Card 3 */}
            <div className="bg-[#0f172a] border border-outline-variant rounded-lg p-5 shadow flex flex-col justify-between min-h-[220px]">
               <div className="flex flex-col gap-1">
                  <div className="flex justify-between items-center mb-1">
                     <div className="flex items-center gap-2">
                        <span className="px-1.5 py-0.5 bg-[#45e0a0]/10 text-[#45e0a0] rounded font-label-sm text-[9px] uppercase font-bold tracking-widest flex items-center gap-1">
                          <div className="w-1.5 h-1.5 rounded-full bg-[#45e0a0]" /> ACTIVE
                        </span>
                        <span className="px-1.5 py-0.5 bg-surface-container border border-outline-variant rounded font-code-sm text-[10px] text-outline">v3.0.4-prod</span>
                     </div>
                     <span className="font-code-sm text-[10px] text-outline">UUID: <span className="text-on-surface font-bold">ap-4411c</span></span>
                  </div>
                  <h3 className="font-headline-sm text-lg font-bold text-on-surface mt-2">Acoustic Phase Anomaly Detector v3.0</h3>
                  <span className="font-body-sm text-[12px] text-outline">Glottal Pulse Incongruity & Replay Detection</span>
               </div>
               
               <div className="mt-4 flex flex-col gap-2">
                  <div className="flex justify-between font-label-sm text-[9px] uppercase tracking-widest font-bold">
                    <span className="text-outline">GLOTTAL FLOW DERIVATIVE</span>
                    <span className="text-[#00c8e8]">SNR: 34.2dB</span>
                  </div>
                  <div className="h-10 w-full relative border-b border-outline-variant/30">
                     <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={mockLineData}>
                           <Line type="monotone" dataKey="val" stroke="#00c8e8" strokeWidth={2} dot={false} isAnimationActive={false} />
                           <Line type="monotone" dataKey="error" stroke="#ffaaa0" strokeWidth={2} strokeDasharray="3 3" dot={false} isAnimationActive={false} />
                        </LineChart>
                     </ResponsiveContainer>
                  </div>
                  
                  <div className="grid grid-cols-3 gap-2 mt-2">
                     <div className="flex flex-col">
                       <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest">ACCURACY</span>
                       <span className="font-code-sm text-[13px] text-on-surface font-bold">96.1%</span>
                     </div>
                     <div className="flex flex-col">
                       <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest">LATENCY</span>
                       <span className="font-code-sm text-[13px] text-[#00c8e8] font-bold">3.2ms</span>
                     </div>
                     <div className="flex flex-col">
                       <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest">ARCHITECTURE</span>
                       <span className="font-code-sm text-[11px] text-on-surface font-bold mt-0.5">Dilated Conv Wave</span>
                     </div>
                  </div>
               </div>

               <div className="flex justify-between items-center border-t border-outline-variant/30 pt-4 mt-4">
                  <span className="font-label-sm text-[10px] text-outline">Updated 1 week ago</span>
                  <div className="flex items-center gap-4 font-label-sm text-[11px] font-bold">
                     <button className="text-outline hover:text-on-surface underline transition-colors">Inspect Weights</button>
                     <button className="flex items-center gap-1 text-[#00c8e8] hover:text-[#00c8e8]/80 transition-colors">Threshold Config <SlidersHorizontal className="w-3 h-3"/></button>
                  </div>
               </div>
            </div>

            {/* Model Card 4 */}
            <div className="bg-[#0f172a] border border-outline-variant rounded-lg p-5 shadow flex flex-col justify-between min-h-[220px]">
               <div className="flex flex-col gap-1">
                  <div className="flex justify-between items-center mb-1">
                     <div className="flex items-center gap-2">
                        <span className="px-1.5 py-0.5 bg-[#45e0a0]/10 text-[#45e0a0] rounded font-label-sm text-[9px] uppercase font-bold tracking-widest flex items-center gap-1">
                          <div className="w-1.5 h-1.5 rounded-full bg-[#45e0a0]" /> ACTIVE
                        </span>
                        <span className="px-1.5 py-0.5 bg-surface-container border border-outline-variant rounded font-code-sm text-[10px] text-outline">v5.1.0-prod</span>
                     </div>
                     <span className="font-code-sm text-[10px] text-outline">UUID: <span className="text-on-surface font-bold">rf-9905d</span></span>
                  </div>
                  <h3 className="font-headline-sm text-lg font-bold text-on-surface mt-2">Neural Impersonation Risk Fusion Engine</h3>
                  <span className="font-body-sm text-[12px] text-outline">Multi-vector Threat Scoring & Real-time Bayesian Aggregation</span>
               </div>
               
               <div className="mt-4 flex flex-col gap-2">
                  <div className="flex flex-col gap-1 p-3 bg-[#1e293b]/50 border border-outline-variant/50 rounded text-center relative">
                     <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest font-bold">BAYESIAN CALIBRATION INDEX</span>
                     <span className="font-headline-sm text-2xl text-on-surface font-bold">99.1% <span className="text-lg text-outline font-normal">Confidence</span></span>
                     <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-1 font-label-sm text-[9px] text-[#45e0a0] font-bold tracking-widest uppercase">
                       <div className="w-1.5 h-1.5 rounded-full bg-[#45e0a0]" /> CONVERGED
                     </div>
                  </div>
                  
                  <div className="grid grid-cols-3 gap-2 mt-2">
                     <div className="flex flex-col">
                       <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest">AGGREGATION</span>
                       <span className="font-code-sm text-[11px] text-on-surface font-bold mt-0.5">Multi-Vector</span>
                     </div>
                     <div className="flex flex-col">
                       <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest">LATENCY</span>
                       <span className="font-code-sm text-[13px] text-[#00c8e8] font-bold">1.8ms</span>
                     </div>
                     <div className="flex flex-col">
                       <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest">DECISION RATE</span>
                       <span className="font-code-sm text-[11px] text-on-surface font-bold mt-0.5">4.2k evals/s</span>
                     </div>
                  </div>
               </div>

               <div className="flex justify-between items-center border-t border-outline-variant/30 pt-4 mt-4">
                  <span className="font-label-sm text-[10px] text-outline">Updated 18 hours ago</span>
                  <div className="flex items-center gap-4 font-label-sm text-[11px] font-bold">
                     <button className="text-outline hover:text-on-surface underline transition-colors">Model Logs</button>
                     <button className="flex items-center gap-1 text-[#00c8e8] hover:text-[#00c8e8]/80 transition-colors">Rule Tuning <SlidersHorizontal className="w-3 h-3"/></button>
                  </div>
               </div>
            </div>
         </div>
      </div>

      <div className="flex items-center gap-2 bg-[#0f172a] border border-outline-variant/50 rounded-lg p-3 mt-2">
         <LayoutGrid className="w-4 h-4 text-[#00c8e8]" />
         <span className="font-body-sm text-[11px] text-on-surface font-bold">Telemetry & Codec Performance Benchmarks</span>
         <span className="ml-auto font-code-sm text-[10px] text-outline">Dataset: <span className="text-on-surface">VoxCeleb-Synth24 (v1.4)</span></span>
      </div>

    </div>
  );
};

export default AIModelCenter;
