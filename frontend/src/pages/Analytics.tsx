import { BarChart2 } from 'lucide-react';

const Analytics = () => {
  return (
    <div className="flex flex-col w-full h-full gap-5">
      <div className="flex items-end justify-between pb-3 border-b border-outline-variant">
        <div className="flex flex-col gap-1">
          <span className="font-label-sm text-[10px] text-primary tracking-widest uppercase">FORENSICS / ANALYTICS</span>
          <h1 className="font-headline-xl text-2xl text-on-surface tracking-tight font-semibold">Security Analytics</h1>
          <p className="font-body-sm text-xs text-outline mt-1">Historical threat trends and system performance.</p>
        </div>
      </div>

      <div className="flex-1 bg-surface-container border border-outline-variant rounded p-5 flex flex-col items-center justify-center text-outline">
         <BarChart2 className="w-12 h-12 mb-3 opacity-20" />
         <p className="font-body-sm text-sm">Historical analytics charts would render here.</p>
      </div>
    </div>
  );
};

export default Analytics;
