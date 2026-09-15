import { Settings as SettingsIcon } from 'lucide-react';

const Settings = () => {
  return (
    <div className="flex flex-col w-full h-full gap-5">
      <div className="flex items-end justify-between pb-3 border-b border-outline-variant">
        <div className="flex flex-col gap-1">
          <span className="font-label-sm text-[10px] text-primary tracking-widest uppercase">FORENSICS / CONFIGURATION</span>
          <h1 className="font-headline-xl text-2xl text-on-surface tracking-tight font-semibold">Settings</h1>
          <p className="font-body-sm text-xs text-outline mt-1">Global security thresholds and account management.</p>
        </div>
      </div>

      <div className="flex-1 bg-surface-container border border-outline-variant rounded p-5 flex flex-col items-center justify-center text-outline">
         <SettingsIcon className="w-12 h-12 mb-3 opacity-20" />
         <p className="font-body-sm text-sm">Settings form controls would render here.</p>
      </div>
    </div>
  );
};

export default Settings;
