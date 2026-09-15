import { Server, PhoneCall, Globe } from 'lucide-react';

const Integrations = () => {
  const integrations = [
    { name: 'SIP/RTP Gateway', type: 'Telephony', status: 'CONNECTED', endpoint: 'sip:vshield.enterprise.local', icon: PhoneCall },
    { name: 'WebRTC Proxy', type: 'Browser Communications', status: 'CONNECTED', endpoint: 'wss://webrtc.vshield.net', icon: Globe },
    { name: 'Enterprise Identity', type: 'Backend API', status: 'SYNCED', endpoint: 'https://idp.enterprise.local/api/v1', icon: Server },
  ];

  return (
    <div className="flex flex-col w-full h-full gap-5">
      <div className="flex items-end justify-between pb-3 border-b border-outline-variant">
        <div className="flex flex-col gap-1">
          <span className="font-label-sm text-[10px] text-primary tracking-widest uppercase">FORENSICS / INTEGRATIONS</span>
          <h1 className="font-headline-xl text-2xl text-on-surface tracking-tight font-semibold">Integrations</h1>
          <p className="font-body-sm text-xs text-outline mt-1">Manage external connections and telemetry ingest pipelines.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        {integrations.map((int) => {
          const Icon = int.icon;
          return (
            <div key={int.name} className="bg-surface-container border border-outline-variant rounded p-5 flex flex-col gap-4">
              <div className="flex justify-between items-start">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded bg-surface-container-highest border border-outline-variant">
                    <Icon className="w-5 h-5 text-on-surface" />
                  </div>
                  <div className="flex flex-col">
                    <span className="font-headline-sm text-sm text-on-surface font-semibold">{int.name}</span>
                    <span className="font-label-sm text-[10px] text-outline">{int.type}</span>
                  </div>
                </div>
                <span className={`font-label-sm text-[9px] tracking-widest px-2 py-0.5 rounded border ${int.status === 'CONNECTED' ? 'bg-tertiary/10 text-tertiary border-tertiary/20' : 'bg-primary/10 text-primary border-primary/20'}`}>
                  {int.status}
                </span>
              </div>

              <div className="flex flex-col gap-1 pt-4 border-t border-outline-variant/50">
                <span className="font-label-sm text-[9px] text-outline uppercase tracking-wider">Endpoint</span>
                <span className="font-code-md text-xs text-on-surface">{int.endpoint}</span>
              </div>
              
              <div className="mt-2 flex justify-end">
                <button className="px-3 py-1.5 rounded bg-surface-container-highest border border-outline-variant text-xs font-medium hover:bg-surface-container-low transition-colors">
                  Configure
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default Integrations;
