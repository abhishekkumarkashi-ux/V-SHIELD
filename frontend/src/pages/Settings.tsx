import { Settings as SettingsIcon, Save } from 'lucide-react';

const Settings = () => {
  return (
    <div className="space-y-6 max-w-4xl">
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
        <h3 className="text-lg font-medium text-slate-200 mb-6 flex items-center gap-2">
          <SettingsIcon className="w-5 h-5 text-slate-400" />
          Engine Configuration
        </h3>
        
        <div className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">VAD Sensitivity</label>
            <input type="range" min="1" max="100" defaultValue="50" className="w-full accent-blue-500" disabled />
            <p className="text-xs text-slate-500 mt-1">Configured on backend only.</p>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Risk Escallation Threshold</label>
            <select className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 focus:outline-none focus:border-blue-500" disabled>
              <option>Strict (3 windows)</option>
              <option>Normal (5 windows)</option>
              <option>Relaxed (10 windows)</option>
            </select>
            <p className="text-xs text-slate-500 mt-1">Temporarily disabled while in read-only mode.</p>
          </div>
        </div>

        <div className="mt-8 pt-6 border-t border-slate-800 flex justify-end">
          <button disabled className="bg-blue-600/50 text-white/50 px-4 py-2 rounded-lg flex items-center gap-2 cursor-not-allowed">
            <Save className="w-4 h-4" />
            Save Changes
          </button>
        </div>
      </div>
    </div>
  );
};

export default Settings;
