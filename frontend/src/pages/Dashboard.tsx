import { useState, useEffect } from 'react';
import { ShieldCheck, Activity, Download } from 'lucide-react';
import { apiService } from '../services/api';
import ThreatActivityChart from '../components/dashboard/ThreatActivityChart';
import DefensePosture from '../components/dashboard/DefensePosture';
import IncidentTable from '../components/dashboard/IncidentTable';

const Dashboard = () => {
  const [history, setHistory] = useState<any[]>([]);

  useEffect(() => {
    apiService.getHistory()
      .then(data => {
        const histData = data?.history || data || [];
        setHistory(Array.isArray(histData) ? histData : []);
      })
      .catch(console.error);
  }, []);

  const callsAnalyzed = history.length;
  const threatsIntercepted = history.filter(h => h.risk_level === 'HIGH' || h.risk_level === 'CRITICAL').length;
  const avgRiskScore = callsAnalyzed > 0 
    ? (history.reduce((acc, curr) => acc + (curr.risk_score || 0), 0) / callsAnalyzed * 100).toFixed(1) 
    : '0.0';

  return (
    <div className="flex flex-col w-full h-full gap-5">
      {/* Page Header */}
      <div className="flex items-end justify-between pb-3">
        <div className="flex flex-col gap-1">
          <span className="font-label-sm text-[10px] text-primary tracking-widest uppercase font-bold">DEFENSIVE TELEMETRY / <span className="text-outline">NODE US-EAST-01</span></span>
          <h1 className="font-headline-xl text-3xl text-on-surface tracking-tight font-semibold">Security Overview</h1>
          <p className="font-body-sm text-sm text-outline mt-1">Real-time visibility into your enterprise voice security environment.</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="bg-surface-container border border-outline-variant rounded flex items-center px-3 py-2 text-xs text-on-surface cursor-pointer hover:border-outline transition-colors">
             <span className="text-primary mr-2">📅</span>
             Last 24 Hours
             <span className="ml-2 opacity-50">▼</span>
          </div>
          <button className="flex items-center gap-2 bg-primary/10 text-primary border border-primary/20 hover:bg-primary/20 hover:border-primary/40 px-4 py-2 rounded transition-colors">
            <Download className="w-4 h-4" />
            <span className="font-label-sm text-xs tracking-wider uppercase font-bold">Export SOC Report</span>
          </button>
        </div>
      </div>

      {/* Metric Cards Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-5">
        {/* Card 1: Protected Streams */}
        <div className="bg-[#0f172a] rounded-lg border border-outline-variant p-5 flex flex-col justify-between h-[140px] shrink-0 shadow-lg">
          <div className="flex items-center justify-between">
            <span className="font-label-sm text-[10px] text-outline tracking-widest uppercase">PROTECTED STREAMS</span>
            <div className="p-1.5 rounded bg-[#00c8e8]/10 border border-[#00c8e8]/20 text-[#00c8e8]">
              <ShieldCheck className="w-4 h-4" />
            </div>
          </div>
          <div className="flex items-end justify-between mt-2">
            <div className="flex flex-col">
              <span className="font-headline-sm text-[2.5rem] font-bold tracking-tight text-on-surface leading-none mb-1">
                {callsAnalyzed.toLocaleString()}
              </span>
              <div className="flex items-center gap-1 mt-2">
                <span className="text-[#45e0a0] text-sm">↑</span>
                <span className="text-[#45e0a0] font-label-sm text-xs">+12.4%</span>
                <span className="font-label-sm text-[10px] text-outline ml-1">last<br/>week</span>
              </div>
            </div>
            {/* Sparkline approximation */}
            <div className="w-24 h-8 flex items-end">
               <svg viewBox="0 0 100 30" className="w-full h-full stroke-[#45e0a0]" fill="none" strokeWidth="2">
                 <path d="M0 25 L20 22 L40 28 L60 15 L80 18 L100 5" />
               </svg>
            </div>
          </div>
        </div>

        {/* Card 2: Threats Intercepted */}
        <div className="bg-[#0f172a] rounded-lg border border-outline-variant p-5 flex flex-col justify-between h-[140px] shrink-0 shadow-lg relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="font-label-sm text-[10px] text-outline tracking-widest uppercase">THREATS INTERCEPTED</span>
          </div>
          <div className="flex items-end justify-between mt-2">
            <div className="flex flex-col w-full">
              <span className="font-headline-sm text-[2.5rem] font-bold tracking-tight text-[#ffaaa0] leading-none mb-1">
                {threatsIntercepted}
              </span>
              <div className="flex flex-col w-full mt-2">
                <div className="flex items-center justify-between text-[10px] font-label-sm text-outline mb-1">
                  <div className="flex items-center gap-1">
                    <span className="text-[#45e0a0] text-xs">↓</span>
                    <span className="text-[#45e0a0]">-4.2% w/w</span>
                  </div>
                  <div className="flex gap-1.5">
                     <span><span className="text-[#ffaaa0]">32</span> Synth</span>
                     <span>/ <span className="text-[#ffaaa0]">11</span> Clone</span>
                     <span>/ <span className="text-[#ffaaa0]">4</span> Spf</span>
                  </div>
                </div>
                {/* Segmented Bar */}
                <div className="h-1.5 w-full flex gap-[2px] mt-1">
                  <div className="h-full bg-[#ffaaa0] rounded-l" style={{width: '68%'}}></div>
                  <div className="h-full bg-[#ffaaa0]/70" style={{width: '23%'}}></div>
                  <div className="h-full bg-[#ffaaa0]/40 rounded-r" style={{width: '9%'}}></div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Card 3: Calls Analyzed */}
        <div className="bg-[#0f172a] rounded-lg border border-outline-variant p-5 flex flex-col justify-between h-[140px] shrink-0 shadow-lg">
          <div className="flex items-center justify-between">
            <span className="font-label-sm text-[10px] text-outline tracking-widest uppercase">CALLS ANALYZED</span>
            <div className="p-1.5 rounded bg-[#94a3b8]/10 border border-[#94a3b8]/20 text-[#94a3b8]">
              <Activity className="w-4 h-4" />
            </div>
          </div>
          <div className="flex items-end justify-between mt-2">
            <div className="flex flex-col">
              <span className="font-headline-sm text-[2.5rem] font-bold tracking-tight text-on-surface leading-none mb-1">
                {callsAnalyzed.toLocaleString()}
              </span>
              <div className="flex items-center gap-6 mt-2">
                <div className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-[#45e0a0]"></div>
                  <div className="flex flex-col">
                    <span className="font-label-sm text-[10px] text-outline uppercase leading-tight">PIPELINE</span>
                    <span className="font-label-sm text-[10px] text-outline uppercase leading-tight">VELOCITY</span>
                  </div>
                </div>
                <div className="flex flex-col text-right">
                  <span className="font-label-sm text-xs text-[#00c8e8] font-bold leading-tight">99.98%</span>
                  <span className="font-label-sm text-[10px] text-outline uppercase leading-tight">SLA</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Card 4: Average Risk Score */}
        <div className="bg-[#0f172a] rounded-lg border border-outline-variant p-5 flex flex-col justify-between h-[140px] shrink-0 shadow-lg">
          <div className="flex items-center justify-between">
            <span className="font-label-sm text-[10px] text-outline tracking-widest uppercase">AVERAGE RISK SCORE</span>
            <div className="p-1.5 rounded bg-[#45e0a0]/10 border border-[#45e0a0]/20 text-[#45e0a0]">
              <ShieldCheck className="w-4 h-4" />
            </div>
          </div>
          <div className="flex items-end justify-between mt-2">
            <div className="flex flex-col w-full">
              <div className="flex items-baseline gap-1 mb-1">
                <span className="font-headline-sm text-[2.5rem] font-bold tracking-tight text-[#45e0a0] leading-none">
                  {avgRiskScore}
                </span>
                <span className="font-label-sm text-xs text-outline">/ 100</span>
              </div>
              <div className="flex items-center justify-between mt-2 border-t border-outline-variant/50 pt-2">
                <div className="flex flex-col">
                  <span className="font-label-sm text-[10px] text-[#45e0a0] uppercase tracking-wider font-bold leading-tight">OPTIMAL</span>
                  <span className="font-label-sm text-[10px] text-[#45e0a0] uppercase tracking-wider font-bold leading-tight">POSTURE</span>
                </div>
                <div className="flex flex-col text-right">
                  <span className="font-label-sm text-[10px] text-outline uppercase leading-tight">Threshold &lt;</span>
                  <span className="font-label-sm text-[10px] text-outline uppercase leading-tight">40.0</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        {/* Left Column (Chart + Table) */}
        <div className="xl:col-span-2 flex flex-col gap-5">
          <ThreatActivityChart history={history} />
          <IncidentTable history={history} />
        </div>
        
        {/* Right Column (Defense Posture) */}
        <div className="xl:col-span-1 flex flex-col gap-5">
          <DefensePosture history={history} />
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
