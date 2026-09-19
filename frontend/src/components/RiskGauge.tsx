import React from 'react';
import { ShieldCheck, ShieldAlert, AlertTriangle } from 'lucide-react';

interface RiskGaugeProps {
  score: number; // 0 to 100
  classification: 'LOW_RISK' | 'MEDIUM_RISK' | 'HIGH_RISK';
}

export const RiskGauge: React.FC<RiskGaugeProps> = ({ score, classification }) => {
  // Clamp score
  const clampedScore = Math.max(0, Math.min(100, score));

  // Gauge angles: -90 deg (left, score 0) to +90 deg (right, score 100)
  // Total arc = 180 degrees
  const angle = -90 + (clampedScore / 100) * 180;

  // Arc stroke dasharray calculation (semi-circle radius = 80, length = PI * 80 ~= 251.32)
  const radius = 80;
  const circumference = Math.PI * radius;
  const strokeDashoffset = circumference - (clampedScore / 100) * circumference;

  let themeColor = '#10b981'; // Emerald
  let glowColor = 'rgba(16, 185, 129, 0.4)';
  let bgBadge = 'bg-emerald-950/80 border-emerald-500/40 text-emerald-300';
  let statusText = 'VERIFIED GENUINE';
  let Icon = ShieldCheck;

  if (classification === 'HIGH_RISK') {
    themeColor = '#ef4444'; // Crimson
    glowColor = 'rgba(239, 68, 68, 0.45)';
    bgBadge = 'bg-red-950/80 border-red-500/40 text-red-400';
    statusText = 'VOICE CLONE DETECTED';
    Icon = ShieldAlert;
  } else if (classification === 'MEDIUM_RISK') {
    themeColor = '#f59e0b'; // Amber
    glowColor = 'rgba(245, 158, 11, 0.4)';
    bgBadge = 'bg-amber-950/80 border-amber-500/40 text-amber-300';
    statusText = 'SUSPICIOUS / UNVERIFIED';
    Icon = AlertTriangle;
  }

  return (
    <div className="flex flex-col items-center justify-center relative p-4">
      {/* SVG Semi-Circular Gauge */}
      <div className="relative w-64 h-36 flex items-center justify-center">
        <svg
          viewBox="0 0 200 115"
          className="w-full h-full overflow-visible drop-shadow-[0_4px_12px_rgba(0,0,0,0.5)]"
        >
          <defs>
            <linearGradient id="gaugeGradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#10b981" />
              <stop offset="35%" stopColor="#10b981" />
              <stop offset="60%" stopColor="#f59e0b" />
              <stop offset="85%" stopColor="#ef4444" />
              <stop offset="100%" stopColor="#dc2626" />
            </linearGradient>
            <filter id="gaugeGlow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
          </defs>

          {/* Background Track Arc */}
          <path
            d="M 20 100 A 80 80 0 0 1 180 100"
            fill="none"
            stroke="#1a2747"
            strokeWidth="14"
            strokeLinecap="round"
          />

          {/* Dynamic Active Progress Arc */}
          <path
            d="M 20 100 A 80 80 0 0 1 180 100"
            fill="none"
            stroke="url(#gaugeGradient)"
            strokeWidth="14"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            className="transition-all duration-300 ease-out"
            filter="url(#gaugeGlow)"
          />

          {/* Threshold Tick Marks */}
          <line x1="20" y1="100" x2="30" y2="100" stroke="#475569" strokeWidth="1.5" />
          <line x1="100" y1="20" x2="100" y2="30" stroke="#475569" strokeWidth="1.5" />
          <line x1="170" y1="100" x2="180" y2="100" stroke="#475569" strokeWidth="1.5" />

          {/* Needle Center Pivot */}
          <circle cx="100" cy="100" r="7" fill="#0f172a" stroke={themeColor} strokeWidth="2.5" />
          
          {/* Animated Needle */}
          <g
            style={{
              transform: `rotate(${angle}deg)`,
              transformOrigin: '100px 100px',
              transition: 'transform 0.35s cubic-bezier(0.34, 1.56, 0.64, 1)',
            }}
          >
            <line
              x1="100"
              y1="100"
              x2="100"
              y2="28"
              stroke={themeColor}
              strokeWidth="3.5"
              strokeLinecap="round"
            />
            <polygon
              points="97,35 103,35 100,24"
              fill={themeColor}
            />
          </g>
        </svg>

        {/* Ambient Glow beneath gauge */}
        <div
          className="absolute -bottom-2 w-36 h-8 rounded-full blur-xl pointer-events-none transition-all duration-500"
          style={{ backgroundColor: glowColor }}
        />
      </div>

      {/* Numerical Display & Status Badge */}
      <div className="flex flex-col items-center mt-2">
        <div className="flex items-baseline space-x-1">
          <span className="text-4xl font-extrabold font-mono tracking-tight" style={{ color: themeColor }}>
            {clampedScore.toFixed(1)}
          </span>
          <span className="text-sm font-semibold text-slate-400">/100</span>
        </div>

        <div className={`mt-2 px-3 py-1 rounded-full border text-xs font-bold uppercase tracking-wider flex items-center space-x-1.5 ${bgBadge}`}>
          <Icon className="w-3.5 h-3.5" />
          <span>{statusText}</span>
        </div>
      </div>
    </div>
  );
};
