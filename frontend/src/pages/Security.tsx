import { useState, useEffect } from 'react';
import { apiService, healthService } from '../services/api';

const Security = () => {
  const [status, setStatus] = useState<any>(null);
  const [dbStatus, setDbStatus] = useState('Checking...');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      apiService.getStatus().catch(() => null),
      healthService.check().catch(() => ({ database: 'offline' }))
    ]).then(([statusRes, dbRes]) => {
      setStatus(statusRes);
      setDbStatus(dbRes?.database === 'connected' ? 'Connected' : 'Offline');
    }).finally(() => setLoading(false));
  }, []);

  const statuses = [
    { name: 'Anti-Spoofing Engine', status: status?.ml_model?.impersonation_model ? 'Operational' : 'Offline', icon: 'smart_toy', color: 'text-tertiary', bg: 'bg-tertiary/10 border-tertiary/20' },
    { name: 'Speaker Verification', status: status?.ml_model?.speaker_verification ? 'Operational' : 'Offline', icon: 'how_to_reg', color: 'text-tertiary', bg: 'bg-tertiary/10 border-tertiary/20' },
    { name: 'Real-Time Engine', status: status?.system === 'online' ? 'Connected' : 'Offline', icon: 'speed', color: 'text-primary', bg: 'bg-primary/10 border-primary/20' },
    { name: 'Backend API', status: status?.system === 'online' ? 'Connected' : 'Offline', icon: 'api', color: 'text-primary', bg: 'bg-primary/10 border-primary/20' },
    { name: 'Database', status: dbStatus, icon: 'database', color: 'text-primary', bg: 'bg-primary/10 border-primary/20' },
  ];

  return (
    <div className="flex flex-col w-full max-w-4xl gap-space-lg">
      <div className="flex flex-col gap-1 pb-space-xs border-b border-outline-variant">
        <h1 className="font-headline-xl text-headline-xl text-on-surface tracking-tight">System Security</h1>
        <p className="font-body-md text-body-md text-outline">Real-time health status of V-SHIELD core microservices and ML models.</p>
      </div>

      <div className="bg-surface-container border border-outline-variant rounded-xl p-space-lg shadow-sm">
        <h3 className="font-headline-sm text-headline-sm text-on-surface mb-6 flex items-center gap-2">
          <span className="material-symbols-outlined text-[24px] text-primary">security</span>
          Core Infrastructure
        </h3>
        
        <div className="flex flex-col gap-space-sm">
          {loading ? (
             <div className="py-12 flex justify-center">
               <span className="material-symbols-outlined text-[32px] text-primary animate-spin">sync</span>
             </div>
          ) : (
            statuses.map((item, i) => {
              const isGood = item.status === 'Operational' || item.status === 'Connected';
              return (
                <div key={i} className="flex items-center justify-between p-4 rounded-lg bg-surface-container-lowest border border-outline-variant transition-colors hover:bg-surface-container-highest">
                  <div className="flex items-center gap-4">
                    <div className={`p-2 rounded-md border ${item.bg} flex items-center justify-center`}>
                      <span className={`material-symbols-outlined text-[20px] ${item.color}`}>{item.icon}</span>
                    </div>
                    <span className="font-headline-sm text-body-md text-on-surface">{item.name}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`w-2.5 h-2.5 rounded-full ${isGood ? 'bg-tertiary shadow-[0_0_8px_rgba(78,222,163,0.6)]' : 'bg-error animate-pulse shadow-[0_0_8px_rgba(255,180,171,0.6)]'}`}></span>
                    <span className={`font-label-md text-label-sm uppercase tracking-wider ${isGood ? 'text-outline' : 'text-error'}`}>{item.status}</span>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};

export default Security;
