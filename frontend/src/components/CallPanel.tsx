import React, { useRef } from 'react';
import { PhoneCall, UserCheck, Bot, Upload } from 'lucide-react';

interface CallPanelProps {
  onFileUpload?: (event: React.ChangeEvent<HTMLInputElement>) => void;
  isAnalyzing?: boolean;
  result?: any;
}

const CallPanel: React.FC<CallPanelProps> = ({ onFileUpload, isAnalyzing, result }) => {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const humanProb = result ? Math.round((1 - result.spoof_probability) * 100) : '--';
  const aiProb = result ? Math.round(result.spoof_probability * 100) : '--';
  
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 h-full flex flex-col">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-slate-200 font-medium flex items-center space-x-2">
          <PhoneCall className="w-5 h-5 text-blue-400" />
          <span>Active Call Analysis</span>
        </h3>
        <span className="bg-green-500/20 text-green-400 text-xs px-2 py-1 rounded-md border border-green-500/30">
          LIVE
        </span>
      </div>

      <div className="space-y-6 flex-1">
        <div className="bg-slate-800/50 p-4 rounded-lg border border-slate-700">
          <div className="flex items-center justify-between mb-2">
            <span className="text-slate-400 text-sm">Target Identity</span>
            <span className="text-slate-200 font-medium">Unknown Caller</span>
          </div>
          <div className="w-full bg-slate-700 rounded-full h-1.5 mb-1 mt-3">
            <div className={`h-1.5 rounded-full ${result?.prediction === 'spoof' ? 'bg-red-500' : 'bg-blue-500'}`} style={{ width: result ? '100%' : '45%' }}></div>
          </div>
          <p className="text-xs text-slate-500 text-right">Speaker Verification Confidence: {result ? '100%' : '--%'}</p>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="bg-slate-800/50 p-4 rounded-lg border border-slate-700 flex flex-col items-center justify-center">
            <UserCheck className={`w-8 h-8 mb-2 ${result?.prediction === 'bonafide' ? 'text-green-400' : 'text-slate-400'}`} />
            <span className="text-sm text-slate-400">Human Prob.</span>
            <span className="text-xl font-bold text-slate-200">{humanProb}%</span>
          </div>
          <div className="bg-slate-800/50 p-4 rounded-lg border border-slate-700 flex flex-col items-center justify-center">
            <Bot className={`w-8 h-8 mb-2 ${result?.prediction === 'spoof' ? 'text-red-400' : 'text-slate-400'}`} />
            <span className="text-sm text-slate-400">AI Prob.</span>
            <span className="text-xl font-bold text-slate-200">{aiProb}%</span>
          </div>
        </div>
        
        <div className="mt-auto pt-4 border-t border-slate-800 flex justify-center">
          <input 
            type="file" 
            accept="audio/*" 
            className="hidden" 
            ref={fileInputRef} 
            onChange={onFileUpload} 
          />
          <button 
            onClick={() => fileInputRef.current?.click()}
            disabled={isAnalyzing}
            className={`flex items-center space-x-2 px-4 py-2 rounded-lg transition-colors w-full justify-center ${
              isAnalyzing ? 'bg-slate-700 text-slate-400 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-700 text-white'
            }`}
          >
            {isAnalyzing ? (
              <span>Analyzing...</span>
            ) : (
              <>
                <Upload className="w-4 h-4" />
                <span>Upload Audio for Analysis</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

export default CallPanel;
