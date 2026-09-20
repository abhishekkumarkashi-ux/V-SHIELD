import React from 'react';
import { Cpu, Fingerprint, Volume2, Timer } from 'lucide-react';
import { TelemetryMetrics } from '../hooks/useVShieldSocket';

interface TelemetryBreakdownProps {
  metrics: TelemetryMetrics | null;
  enrolledSpeakerName?: string | null;
}

export const TelemetryBreakdown: React.FC<TelemetryBreakdownProps> = ({
  metrics,
  enrolledSpeakerName,
}) => {
  const spoofProb = metrics?.spoof_probability ?? 0.0;
  const speakerSim = metrics?.speaker_similarity ?? null;
  const speakerStatus = metrics?.speaker_status;
  const rmsEnergy = metrics?.buffer_energy_rms ?? 0.0;
  const latency = metrics?.latency_ms ?? 0.0;

  // AASIST Threat Indicator
  const isHighSpoof = spoofProb > 0.65;
  const isLowSpoof = spoofProb < 0.30;

  // ECAPA Biometric Match Indicator
  const hasVoiceprint =
    speakerStatus !== 'NO_VOICEPRINT' && speakerSim !== null && speakerSim !== undefined;
  const isBiometricMatch =
    speakerStatus === 'VERIFIED' || (hasVoiceprint && speakerSim >= 0.70);
  const isBiometricMismatch =
    speakerStatus === 'MISMATCH' || (hasVoiceprint && speakerSim <= 0.40);
  const displayStatus = !hasVoiceprint
    ? 'NO_VOICEPRINT'
    : isBiometricMatch
    ? 'VERIFIED'
    : isBiometricMismatch
    ? 'MISMATCH'
    : 'EVALUATING';

  return (
    <div className="grid grid-cols-2 gap-3 w-full">
      {/* AASIST Worker Card */}
      <div className="glass-panel p-3.5 rounded-xl flex flex-col justify-between border-slate-800/80 hover:border-cyan-500/30 transition-colors">
        <div className="flex items-center justify-between text-xs text-slate-400">
          <div className="flex items-center space-x-1.5">
            <Cpu className="w-3.5 h-3.5 text-cyan-400" />
            <span className="font-semibold uppercase tracking-wider">AASIST Worker</span>
          </div>
          <span className="text-[10px] font-mono text-slate-500">nb_samp: 64.6k</span>
        </div>

        <div className="my-2 flex items-baseline justify-between">
          <span className="text-2xl font-bold font-mono text-slate-100">
            {(spoofProb * 100).toFixed(1)}%
          </span>
          <span
            className={`text-xs font-semibold px-2 py-0.5 rounded ${
              isHighSpoof
                ? 'bg-red-950/80 text-red-400 border border-red-500/30'
                : isLowSpoof
                ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-500/30'
                : 'bg-amber-950/80 text-amber-300 border border-amber-500/30'
            }`}
          >
            {isHighSpoof ? 'SYNTHETIC' : isLowSpoof ? 'NATURAL' : 'SUSPICIOUS'}
          </span>
        </div>

        <div className="w-full bg-slate-900 rounded-full h-1.5 overflow-hidden">
          <div
            className={`h-full transition-all duration-300 ${
              isHighSpoof ? 'bg-red-500' : isLowSpoof ? 'bg-emerald-500' : 'bg-amber-500'
            }`}
            style={{ width: `${Math.min(100, Math.max(2, spoofProb * 100))}%` }}
          />
        </div>
        <span className="text-[11px] text-slate-400 mt-1">P(spoof) Log-odds probability</span>
      </div>

      {/* ECAPA-TDNN Worker Card */}
      <div className="glass-panel p-3.5 rounded-xl flex flex-col justify-between border-slate-800/80 hover:border-purple-500/30 transition-colors">
        <div className="flex items-center justify-between text-xs text-slate-400">
          <div className="flex items-center space-x-1.5">
            <Fingerprint className="w-3.5 h-3.5 text-purple-400" />
            <span className="font-semibold uppercase tracking-wider">ECAPA-TDNN</span>
          </div>
          <span className="text-[10px] font-mono text-slate-500">192-dim</span>
        </div>

        <div className="my-2 flex items-baseline justify-between">
          <span className="text-2xl font-bold font-mono text-slate-100">
            {hasVoiceprint && speakerSim !== null ? speakerSim.toFixed(3) : '—'}
          </span>
          <span
            className={`text-xs font-semibold px-2 py-0.5 rounded ${
              !hasVoiceprint
                ? 'bg-slate-800/80 text-slate-400 border border-slate-700/50'
                : isBiometricMatch
                ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-500/30'
                : isBiometricMismatch
                ? 'bg-red-950/80 text-red-400 border border-red-500/30'
                : 'bg-amber-950/80 text-amber-300 border border-amber-500/30'
            }`}
          >
            {displayStatus}
          </span>
        </div>

        <div className="w-full bg-slate-900 rounded-full h-1.5 overflow-hidden">
          <div
            className={`h-full transition-all duration-300 ${
              !hasVoiceprint ? 'bg-slate-700' : isBiometricMatch ? 'bg-emerald-500' : isBiometricMismatch ? 'bg-red-500' : 'bg-amber-500'
            }`}
            style={{ width: `${hasVoiceprint ? Math.min(100, Math.max(0, ((speakerSim + 1) / 2) * 100)) : 0}%` }}
          />
        </div>
        <span className="text-[11px] text-slate-400 mt-1 truncate">
          {hasVoiceprint
            ? enrolledSpeakerName
              ? `vs. ${enrolledSpeakerName}`
              : 'Enrolled speaker verified'
            : 'No enrolled voiceprint active'}
        </span>
      </div>

      {/* RMS Energy Card */}
      <div className="glass-panel p-3.5 rounded-xl flex flex-col justify-between border-slate-800/80">
        <div className="flex items-center space-x-1.5 text-xs text-slate-400">
          <Volume2 className="w-3.5 h-3.5 text-blue-400" />
          <span className="font-semibold uppercase tracking-wider">RMS Energy</span>
        </div>
        <div className="my-2">
          <span className="text-xl font-bold font-mono text-slate-200">
            {rmsEnergy.toFixed(4)}
          </span>
        </div>
        <span className="text-[11px] text-slate-500">Active window volume level</span>
      </div>

      {/* Latency Card */}
      <div className="glass-panel p-3.5 rounded-xl flex flex-col justify-between border-slate-800/80">
        <div className="flex items-center space-x-1.5 text-xs text-slate-400">
          <Timer className="w-3.5 h-3.5 text-emerald-400" />
          <span className="font-semibold uppercase tracking-wider">Hop Latency</span>
        </div>
        <div className="my-2 flex items-baseline space-x-1">
          <span className="text-xl font-bold font-mono text-slate-200">
            {latency.toFixed(1)}
          </span>
          <span className="text-xs text-slate-400">ms</span>
        </div>
        <span className="text-[11px] text-slate-500">0.5s sliding hop cadence</span>
      </div>
    </div>
  );
};
