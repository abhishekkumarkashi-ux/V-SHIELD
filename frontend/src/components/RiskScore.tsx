import React from 'react';
import { AlertTriangle, ShieldCheck } from 'lucide-react';

interface RiskScoreProps {
  score: number | null; // 0-100
  level: 'LOW' | 'MEDIUM' | 'HIGH' | 'UNKNOWN';
}

const RiskScore: React.FC<RiskScoreProps> = ({ score, level }) => {
  const getColor = () => {
    switch (level) {
      case 'LOW': return 'text-green-500';
      case 'MEDIUM': return 'text-yellow-500';
      case 'HIGH': return 'text-red-500';
      default: return 'text-slate-400';
    }
  };

  const getBgColor = () => {
    switch (level) {
      case 'LOW': return 'bg-green-500/10 border-green-500/20';
      case 'MEDIUM': return 'bg-yellow-500/10 border-yellow-500/20';
      case 'HIGH': return 'bg-red-500/10 border-red-500/20';
      default: return 'bg-slate-800/50 border-slate-700';
    }
  };

  return (
    <div className={`p-6 rounded-xl border ${getBgColor()} flex flex-col items-center justify-center space-y-4`}>
      <h3 className="text-slate-300 font-medium uppercase tracking-widest text-sm">Overall Risk Score</h3>
      
      <div className="relative flex items-center justify-center">
        {level === 'HIGH' ? (
          <AlertTriangle className={`w-24 h-24 ${getColor()} opacity-20 absolute`} />
        ) : level === 'LOW' ? (
          <ShieldCheck className={`w-24 h-24 ${getColor()} opacity-20 absolute`} />
        ) : null}
        <span className={`text-6xl font-bold ${getColor()} z-10`}>
          {score !== null ? score : '--'}
        </span>
      </div>
      
      <div className={`px-4 py-1 rounded-full text-sm font-semibold tracking-wide border ${getColor()} border-current`}>
        {level} RISK
      </div>
    </div>
  );
};

export default RiskScore;
