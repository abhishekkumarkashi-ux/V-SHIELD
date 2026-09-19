import React, { useRef, useEffect } from 'react';
import { Activity } from 'lucide-react';

interface AudioWaveformProps {
  analyser: AnalyserNode | null;
  isStreaming: boolean;
  rmsVolume: number;
}

export const AudioWaveform: React.FC<AudioWaveformProps> = ({
  analyser,
  isStreaming,
  rmsVolume,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const animationFrameRef = useRef<number | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let phase = 0;

    const render = () => {
      const width = canvas.width;
      const height = canvas.height;

      ctx.clearRect(0, 0, width, height);

      // Draw subtle horizontal center-line
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(0, height / 2);
      ctx.lineTo(width, height / 2);
      ctx.stroke();

      if (!isStreaming) {
        // Idle flat line with subtle breathe
        ctx.strokeStyle = '#253866';
        ctx.lineWidth = 2;
        ctx.beginPath();
        for (let x = 0; x < width; x += 4) {
          const y = height / 2 + Math.sin((x * 0.02) + phase) * 1.5;
          if (x === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.stroke();
        phase += 0.02;
        animationFrameRef.current = requestAnimationFrame(render);
        return;
      }

      if (analyser) {
        // Live microphone frequency data
        const bufferLength = analyser.frequencyBinCount;
        const dataArray = new Uint8Array(bufferLength);
        analyser.getByteTimeDomainData(dataArray);

        const gradient = ctx.createLinearGradient(0, 0, width, 0);
        gradient.addColorStop(0, '#06b6d4');
        gradient.addColorStop(0.5, '#3b82f6');
        gradient.addColorStop(1, '#8b5cf6');

        ctx.lineWidth = 2.5;
        ctx.strokeStyle = gradient;
        ctx.shadowColor = '#06b6d4';
        ctx.shadowBlur = 8;
        ctx.beginPath();

        const sliceWidth = width / bufferLength;
        let x = 0;

        for (let i = 0; i < bufferLength; i++) {
          const v = dataArray[i] / 128.0;
          const y = (v * height) / 2;

          if (i === 0) {
            ctx.moveTo(x, y);
          } else {
            ctx.lineTo(x, y);
          }

          x += sliceWidth;
        }

        ctx.stroke();
        ctx.shadowBlur = 0; // reset
      } else {
        // Synthetic / simulation wave visualization using rmsVolume
        const gradient = ctx.createLinearGradient(0, 0, width, 0);
        gradient.addColorStop(0, '#06b6d4');
        gradient.addColorStop(1, '#ec4899');

        ctx.lineWidth = 2.5;
        ctx.strokeStyle = gradient;
        ctx.shadowColor = '#06b6d4';
        ctx.shadowBlur = 6;
        ctx.beginPath();

        const amplitude = Math.max(8, rmsVolume * 60);
        for (let x = 0; x < width; x += 3) {
          const y =
            height / 2 +
            Math.sin(x * 0.05 + phase) * amplitude * 0.7 +
            Math.cos(x * 0.12 - phase) * amplitude * 0.3;
          if (x === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.stroke();
        ctx.shadowBlur = 0;
        phase += 0.15;
      }

      animationFrameRef.current = requestAnimationFrame(render);
    };

    render();

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [analyser, isStreaming, rmsVolume]);

  return (
    <div className="w-full relative flex flex-col rounded-xl overflow-hidden glass-panel p-3">
      <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
        <div className="flex items-center space-x-2">
          <Activity className={`w-3.5 h-3.5 ${isStreaming ? 'text-cyan-400 animate-pulse' : 'text-slate-500'}`} />
          <span className="font-semibold uppercase tracking-wider">PCM16 Ingestion Stream</span>
        </div>
        <div className="flex items-center space-x-2 font-mono text-[11px]">
          <span>16,000 Hz</span>
          <span>•</span>
          <span className={isStreaming ? 'text-emerald-400 font-bold' : 'text-slate-500'}>
            {isStreaming ? 'ACTIVE' : 'STANDBY'}
          </span>
        </div>
      </div>

      <div className="relative w-full h-24 bg-[#070b14]/90 rounded-lg border border-slate-800/80 overflow-hidden flex items-center justify-center">
        <canvas
          ref={canvasRef}
          width={600}
          height={96}
          className="w-full h-full block"
        />

        {/* 300ms VAD Margin Preservation Badge Overlay */}
        <div className="absolute bottom-1 right-2 text-[10px] font-mono text-cyan-500/80 bg-cyan-950/40 px-2 py-0.5 rounded border border-cyan-500/20">
          VAD Margin: 300ms
        </div>
      </div>
    </div>
  );
};
