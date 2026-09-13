import React from 'react';
import { AlertCircle, ShieldAlert } from 'lucide-react';

const AlertPanel: React.FC = () => {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-slate-200 font-medium flex items-center space-x-2">
          <ShieldAlert className="w-5 h-5 text-yellow-500" />
          <span>Security Alerts</span>
        </h3>
        <span className="text-xs text-slate-500">Last 24 hours</span>
      </div>

      <div className="space-y-3">
        {/* Placeholder alerts */}
        <div className="bg-yellow-500/10 border border-yellow-500/20 p-3 rounded-lg flex items-start space-x-3">
          <AlertCircle className="w-5 h-5 text-yellow-500 flex-shrink-0 mt-0.5" />
          <div>
            <h4 className="text-sm font-medium text-yellow-500">Anomaly Detected</h4>
            <p className="text-xs text-slate-400 mt-1">Slight spectral artifact detected in current stream. Monitoring closely.</p>
            <span className="text-[10px] text-slate-500 mt-2 block">Just now</span>
          </div>
        </div>

        <div className="bg-slate-800/50 border border-slate-700 p-3 rounded-lg flex items-start space-x-3 opacity-70">
          <ShieldAlert className="w-5 h-5 text-slate-400 flex-shrink-0 mt-0.5" />
          <div>
            <h4 className="text-sm font-medium text-slate-300">System Ready</h4>
            <p className="text-xs text-slate-400 mt-1">V-SHIELD initialized and awaiting audio stream connection.</p>
            <span className="text-[10px] text-slate-500 mt-2 block">2 mins ago</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AlertPanel;
