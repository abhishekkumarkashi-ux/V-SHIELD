import { useMemo } from 'react';
import { AreaChart, Area, XAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { Power } from 'lucide-react';

export interface ThreatActivityChartProps {
  history: any[];
}

const CustomTooltip = ({ active, payload }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-[#1e293b] border border-outline-variant p-2 rounded text-[10px] font-label-sm shadow-xl">
        <p className="text-on-surface mb-1 font-bold">{payload[0].payload.time}</p>
        <p className="text-[#00c8e8]">Clean: {payload[0].value}</p>
        {payload[1] && payload[1].value > 0 && (
          <p className="text-[#ffaaa0]">Threats: {payload[1].value}</p>
        )}
      </div>
    );
  }
  return null;
};

const ThreatActivityChart = ({ history }: ThreatActivityChartProps) => {
  const data = useMemo(() => {
    // Generate buckets for the last 24 hours (8 buckets of 3 hours)
    if (!history || history.length === 0) {
      return [
        { time: '00:00', clean: 0, threat: 0 },
        { time: '06:00', clean: 0, threat: 0 },
        { time: '12:00', clean: 0, threat: 0 },
        { time: '18:00', clean: 0, threat: 0 },
        { time: '23:59', clean: 0, threat: 0 },
      ];
    }
    
    // Simplistic grouping (in a real app, this would use date math relative to now)
    // We will just return some buckets based on timestamps
    const buckets: Record<string, { clean: number, threat: number }> = {
      '00:00': { clean: 0, threat: 0 },
      '06:00': { clean: 0, threat: 0 },
      '12:00': { clean: 0, threat: 0 },
      '18:00': { clean: 0, threat: 0 },
      '23:59': { clean: 0, threat: 0 },
    };
    
    history.forEach(h => {
      const isThreat = h.risk_level === 'HIGH' || h.risk_level === 'CRITICAL';
      const d = new Date(h.timestamp);
      const hour = d.getHours();
      let bucket = '23:59';
      if (hour < 6) bucket = '00:00';
      else if (hour < 12) bucket = '06:00';
      else if (hour < 18) bucket = '12:00';
      else if (hour < 23) bucket = '18:00';
      
      if (isThreat) buckets[bucket].threat++;
      else buckets[bucket].clean++;
    });
    
    return Object.keys(buckets).map(k => ({ time: k, ...buckets[k] }));
  }, [history]);

  // Find peak threat
  let peakThreat: any = null;
  history.forEach(h => {
    if (h.risk_level === 'CRITICAL' || h.risk_level === 'HIGH') {
      if (!peakThreat || h.risk_score > peakThreat.risk_score) {
        peakThreat = h;
      }
    }
  });

  return (
    <div className="bg-[#0f172a] rounded-lg border border-outline-variant p-6 flex flex-col h-[400px] shadow-lg">
      <div className="flex justify-between items-start mb-6">
        <div>
          <h3 className="font-headline-sm text-on-surface text-lg font-semibold tracking-tight">Security Threat Activity</h3>
          <p className="font-body-sm text-[11px] text-outline mt-1 tracking-wide">Real-time acoustic analysis volume vs. intercepted synthetic spikes (24h window)</p>
        </div>
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full bg-[#00c8e8]" />
            <span className="font-label-sm text-[10px] text-on-surface font-semibold tracking-wider">Clean Audio<br/>Stream</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full bg-[#ffaaa0]" />
            <span className="font-label-sm text-[10px] text-on-surface font-semibold tracking-wider">Synthetic<br/>Signatures</span>
          </div>
        </div>
      </div>
      
      <div className="flex-1 w-full relative -ml-4">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 10, right: 0, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="colorClean" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#00c8e8" stopOpacity={0.4}/>
                <stop offset="95%" stopColor="#00c8e8" stopOpacity={0}/>
              </linearGradient>
              <linearGradient id="colorThreat" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#ffaaa0" stopOpacity={0.6}/>
                <stop offset="95%" stopColor="#ffaaa0" stopOpacity={0}/>
              </linearGradient>
            </defs>
            <XAxis 
              dataKey="time" 
              axisLine={{stroke: '#334155'}} 
              tickLine={false} 
              tick={{ fill: '#64748b', fontSize: 10, fontFamily: 'JetBrains Mono', fontWeight: 600 }}
              dy={15}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ stroke: '#334155', strokeWidth: 1, strokeDasharray: '4 4' }} />
            <Area 
              type="monotone" 
              dataKey="clean" 
              stroke="#00c8e8" 
              strokeWidth={3}
              fillOpacity={1} 
              fill="url(#colorClean)" 
              activeDot={{ r: 5, fill: '#00c8e8', stroke: '#0f172a', strokeWidth: 2 }}
            />
            <Area 
              type="linear" 
              dataKey="threat" 
              stroke="#ffaaa0" 
              strokeWidth={2}
              fillOpacity={1} 
              fill="url(#colorThreat)" 
              activeDot={{ r: 5, fill: '#ffaaa0', stroke: '#0f172a', strokeWidth: 2 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      
      {peakThreat && (
        <div className="mt-8 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-1 rounded-full bg-error/10 flex items-center justify-center border border-error/20">
              <Power className="w-4 h-4 text-error" />
            </div>
            <span className="font-body-sm text-xs text-outline">
              Peak synthetic burst detected at <span className="font-label-sm text-[#00c8e8] font-bold">{new Date(peakThreat.timestamp).toLocaleTimeString()}</span> <span className="text-on-surface">(Desk: {peakThreat.target_desk || 'Unknown'})</span>
            </span>
          </div>
          <span className="px-3 py-1 bg-error/10 text-error font-label-sm text-[10px] tracking-widest font-bold border border-error/20 rounded uppercase">
            {peakThreat.risk_level === 'CRITICAL' ? 'BLOCKED' : 'MITIGATED'}
          </span>
        </div>
      )}
    </div>
  );
};

export default ThreatActivityChart;
