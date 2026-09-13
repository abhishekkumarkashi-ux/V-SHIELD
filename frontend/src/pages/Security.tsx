import { Lock, Shield, Server, Database, Brain } from 'lucide-react';

const Security = () => {
  const statuses = [
    { name: 'Anti-Spoofing Engine', status: 'Operational', icon: Brain, color: 'text-emerald-400', bg: 'bg-emerald-400/10' },
    { name: 'Speaker Verification', status: 'Operational', icon: UserCheck, color: 'text-emerald-400', bg: 'bg-emerald-400/10' },
    { name: 'Real-Time Engine', status: 'Connected', icon: Activity, color: 'text-blue-400', bg: 'bg-blue-400/10' },
    { name: 'Backend API', status: 'Connected', icon: Server, color: 'text-blue-400', bg: 'bg-blue-400/10' },
    { name: 'Database', status: 'Connected', icon: Database, color: 'text-blue-400', bg: 'bg-blue-400/10' },
  ];

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
        <h3 className="text-lg font-medium text-slate-200 mb-6 flex items-center gap-2">
          <Shield className="w-5 h-5 text-blue-500" />
          System Security Status
        </h3>
        
        <div className="space-y-4">
          {statuses.map((item, i) => {
            const Icon = item.icon;
            return (
              <div key={i} className="flex items-center justify-between p-4 rounded-lg bg-slate-800/50 border border-slate-700/50">
                <div className="flex items-center gap-4">
                  <div className={`p-2 rounded-md ${item.bg}`}>
                    <Icon className={`w-5 h-5 ${item.color}`} />
                  </div>
                  <span className="font-medium text-slate-200">{item.name}</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full ${item.status === 'Operational' || item.status === 'Connected' ? 'bg-emerald-500' : 'bg-red-500'}`}></div>
                  <span className="text-sm font-medium text-slate-300">{item.status}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

import { UserCheck, Activity } from 'lucide-react';
export default Security;
