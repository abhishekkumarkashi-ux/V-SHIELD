import React from 'react';
import { PhoneCall, ShieldAlert, KeyRound, AlertOctagon, CheckCircle2, PhoneOff } from 'lucide-react';

interface MitigationAlertProps {
  action: string;
  riskScore: number;
  onTriggerMfa?: () => void;
  onTerminateCall?: () => void;
  onOverride?: () => void;
}

export const MitigationAlert: React.FC<MitigationAlertProps> = ({
  action,
  riskScore,
  onTriggerMfa,
  onTerminateCall,
  onOverride,
}) => {
  if (action === 'ALLOW_CALL' || action === 'MONITOR') {
    return (
      <div className="w-full rounded-xl bg-emerald-950/40 border border-emerald-500/30 p-4 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-emerald-500/20 rounded-lg text-emerald-400">
            <CheckCircle2 className="w-5 h-5" />
          </div>
          <div>
            <h4 className="text-sm font-bold text-emerald-300 uppercase tracking-wide">
              Layer 5 Decision: Normal Call Flow
            </h4>
            <p className="text-xs text-slate-400">
              Acoustic and biometric metrics are within safe enterprise operational thresholds.
            </p>
          </div>
        </div>
        <span className="text-xs font-mono font-semibold text-emerald-400 bg-emerald-950 px-3 py-1 rounded-full border border-emerald-500/30">
          PASSED (Risk: {riskScore.toFixed(1)})
        </span>
      </div>
    );
  }

  if (action === 'FLAG_OPERATOR_VERIFICATION' || action === 'STEP_UP_AUTH') {
    return (
      <div className="w-full rounded-xl bg-amber-950/40 border border-amber-500/30 p-4 flex flex-col md:flex-row items-start md:items-center justify-between gap-3">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-amber-500/20 rounded-lg text-amber-400">
            <AlertOctagon className="w-5 h-5" />
          </div>
          <div>
            <h4 className="text-sm font-bold text-amber-300 uppercase tracking-wide">
              Suspicious Voice Signature — Verbal Step-Up Required
            </h4>
            <p className="text-xs text-slate-300">
              Low biometric confidence detected. Instruct caller to provide security pass-phrase.
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2 self-end md:self-auto">
          <button
            onClick={onOverride}
            className="px-3 py-1.5 text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg border border-slate-700 transition"
          >
            Operator Override
          </button>
          <button
            onClick={onTriggerMfa}
            className="px-3 py-1.5 text-xs font-semibold bg-amber-600 hover:bg-amber-500 text-white rounded-lg flex items-center space-x-1 shadow-lg shadow-amber-900/40 transition"
          >
            <KeyRound className="w-3.5 h-3.5" />
            <span>Challenge MFA</span>
          </button>
        </div>
      </div>
    );
  }

  // HIGH RISK: Voice Clone Attack or Synthetic Audio
  return (
    <div className="w-full rounded-xl bg-red-950/50 border border-red-500/50 p-4 shadow-xl shadow-red-950/40 flex flex-col md:flex-row items-start md:items-center justify-between gap-3 animate-pulse-slow">
      <div className="flex items-center space-x-3">
        <div className="p-2 bg-red-600/30 rounded-lg text-red-400 border border-red-500/40">
          <ShieldAlert className="w-6 h-6" />
        </div>
        <div>
          <div className="flex items-center space-x-2">
            <h4 className="text-sm font-extrabold text-red-400 uppercase tracking-wide">
              CRITICAL: Active Voice Clone Impersonation Detected
            </h4>
            <span className="text-[10px] font-bold bg-red-600 text-white px-2 py-0.5 rounded uppercase">
              RISK {riskScore.toFixed(1)}
            </span>
          </div>
          <p className="text-xs text-slate-300 mt-0.5">
            AASIST detected high-probability synthetic voice matching enrolled executive profile. Out-of-band MFA callback triggered automatically.
          </p>
        </div>
      </div>

      <div className="flex items-center space-x-2 self-end md:self-auto">
        <button
          onClick={onTriggerMfa}
          className="px-3 py-1.5 text-xs font-bold bg-red-600 hover:bg-red-500 text-white rounded-lg flex items-center space-x-1 shadow-lg shadow-red-900/60 transition"
        >
          <PhoneCall className="w-3.5 h-3.5" />
          <span>MFA Callback</span>
        </button>
        <button
          onClick={onTerminateCall}
          className="px-3 py-1.5 text-xs font-bold bg-slate-900 hover:bg-red-950 text-red-400 border border-red-500/40 rounded-lg flex items-center space-x-1 transition"
        >
          <PhoneOff className="w-3.5 h-3.5" />
          <span>Quarantine & Drop</span>
        </button>
      </div>
    </div>
  );
};
