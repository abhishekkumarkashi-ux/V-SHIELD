import { useState, useEffect } from 'react';
import { apiService } from '../services/api';
import { History as HistoryIcon, Search, Filter } from 'lucide-react';

const History = () => {
  const [history, setHistory] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiService.getHistory()
      .then(data => {
        const histData = data?.history || data || [];
        setHistory(Array.isArray(histData) ? histData : []);
      })
      .catch(err => console.error(err))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="flex flex-col w-full h-full gap-5">
      <div className="flex items-end justify-between pb-3 border-b border-outline-variant">
        <div className="flex flex-col gap-1">
          <span className="font-label-sm text-[10px] text-primary tracking-widest uppercase">OPERATIONS / AUDIT LOG</span>
          <h1 className="font-headline-xl text-2xl text-on-surface tracking-tight font-semibold">Call History</h1>
          <p className="font-body-sm text-xs text-outline mt-1">Review historical voice sessions and threat assessments.</p>
        </div>
      </div>

      <div className="bg-surface-container border border-outline-variant rounded p-5 flex-1 flex flex-col">
        <div className="flex justify-between items-center mb-4">
          <div className="relative w-64">
            <Search className="w-4 h-4 text-outline absolute left-3 top-1/2 -translate-y-1/2" />
            <input 
              type="text" 
              placeholder="Search call records..." 
              className="bg-surface-container-highest border border-outline-variant rounded px-9 py-1.5 text-xs text-on-surface w-full focus:outline-none focus:border-primary/50 transition-colors"
            />
          </div>
          <div className="flex items-center gap-3">
            <button className="flex items-center gap-2 px-3 py-1.5 rounded bg-surface-container-highest border border-outline-variant text-xs hover:bg-surface-container-low transition-colors text-on-surface">
              <Filter className="w-3.5 h-3.5" />
              Risk Level
            </button>
            <button className="flex items-center gap-2 px-3 py-1.5 rounded bg-surface-container-highest border border-outline-variant text-xs hover:bg-surface-container-low transition-colors text-on-surface">
              <Filter className="w-3.5 h-3.5" />
              Date
            </button>
          </div>
        </div>

        <div className="overflow-x-auto flex-1 border-t border-outline-variant/50 pt-2">
          {loading ? (
             <div className="h-full w-full flex items-center justify-center">
               <HistoryIcon className="w-8 h-8 animate-spin text-outline" />
             </div>
          ) : (
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-outline-variant/50">
                  <th className="py-2 px-3 font-label-sm text-[10px] text-outline font-normal uppercase tracking-wider">CALL ID</th>
                  <th className="py-2 px-3 font-label-sm text-[10px] text-outline font-normal uppercase tracking-wider">CALLER</th>
                  <th className="py-2 px-3 font-label-sm text-[10px] text-outline font-normal uppercase tracking-wider">TIME</th>
                  <th className="py-2 px-3 font-label-sm text-[10px] text-outline font-normal uppercase tracking-wider">RISK SCORE</th>
                  <th className="py-2 px-3 font-label-sm text-[10px] text-outline font-normal uppercase tracking-wider">THREAT</th>
                  <th className="py-2 px-3 font-label-sm text-[10px] text-outline font-normal uppercase tracking-wider text-right">STATUS</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant/30">
                {history.length > 0 ? history.map((session, i) => (
                  <tr key={i} className="hover:bg-surface-container-high transition-colors cursor-pointer">
                    <td className="py-3 px-3 font-code-md text-xs text-primary">CALL-{1000 + i}</td>
                    <td className="py-3 px-3 font-body-sm text-xs text-on-surface">Unknown Caller</td>
                    <td className="py-3 px-3 font-label-sm text-[10px] text-outline">{new Date(session.timestamp).toLocaleString()}</td>
                    <td className="py-3 px-3">
                      <div className="flex items-center gap-1 font-code-md text-[11px]">
                        <span className={session.risk_score * 100 > 80 ? 'text-error' : session.risk_score * 100 > 70 ? 'text-orange-400' : 'text-yellow-400'}>
                          {(session.risk_score * 100).toFixed(1)}
                        </span>
                        <span className="text-outline">/100</span>
                      </div>
                    </td>
                    <td className="py-3 px-3">
                      <span className="font-label-sm text-[9px] text-outline uppercase">
                        {(session.spoof_probability * 100).toFixed(1)}% SYNTH
                      </span>
                    </td>
                    <td className="py-3 px-3 text-right">
                      <span className={`font-label-sm text-[9px] tracking-widest px-2 py-0.5 rounded border ${
                        session.risk_level === 'CRITICAL' ? 'bg-error/10 text-error border-error/20' :
                        session.risk_level === 'HIGH' ? 'bg-orange-500/10 text-orange-400 border-orange-500/20' :
                        'bg-tertiary/10 text-tertiary border-tertiary/20'
                      }`}>
                        {session.risk_level}
                      </span>
                    </td>
                  </tr>
                )) : (
                  <tr>
                    <td colSpan={6} className="py-8 text-center font-body-sm text-outline">No call records found.</td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
};

export default History;
