import React from 'react';

interface MetricCardProps {
  title: string;
  value: string | number;
  icon: React.ElementType;
  supportingText?: string;
  supportingValue?: string;
  supportingLabel?: string;
  accent: 'cyan' | 'red' | 'green';
  breakdown?: { label: string; value: number }[];
}

const MetricCard = ({ title, value, icon: Icon, supportingText, supportingValue, supportingLabel, accent, breakdown }: MetricCardProps) => {
  
  const getAccentColor = () => {
    switch(accent) {
      case 'cyan': return 'text-primary bg-primary/10 border-primary/20';
      case 'red': return 'text-error bg-error/10 border-error/20';
      case 'green': return 'text-tertiary bg-tertiary/10 border-tertiary/20';
    }
  };

  const getAccentTextColor = () => {
    switch(accent) {
      case 'cyan': return 'text-primary';
      case 'red': return 'text-error';
      case 'green': return 'text-tertiary';
    }
  };

  return (
    <div className="bg-surface-container rounded border border-outline-variant p-4 flex flex-col justify-between h-[120px] shrink-0">
      <div className="flex items-center justify-between">
        <span className="font-label-sm text-[10px] text-outline tracking-widest uppercase">{title}</span>
        <div className={`p-1.5 rounded-sm border ${getAccentColor()}`}>
          <Icon className="w-3.5 h-3.5" />
        </div>
      </div>
      
      <div className="flex items-end justify-between mt-2">
        <div className="flex flex-col">
          <span className={`font-headline-sm text-3xl font-bold tracking-tight ${getAccentTextColor()}`}>
            {value}
          </span>
          {supportingText && (
            <div className="flex items-center gap-1 mt-1">
              {accent === 'cyan' && <span className="text-tertiary text-[10px]">↑</span>}
              {accent === 'red' && <span className="text-tertiary text-[10px]">↓</span>}
              <span className="font-label-sm text-[10px] text-outline">{supportingText}</span>
            </div>
          )}
          {breakdown && (
            <div className="flex items-center gap-1.5 mt-1 font-label-sm text-[9px] text-outline tracking-wide">
              {breakdown.map((b, i) => (
                <React.Fragment key={b.label}>
                  <span className={getAccentTextColor()}>{b.value}</span> {b.label}
                  {i < breakdown.length - 1 && <span className="text-outline-variant">/</span>}
                </React.Fragment>
              ))}
            </div>
          )}
          {supportingValue && supportingLabel && (
            <div className="flex items-center gap-2 mt-1">
               <div className={`w-1.5 h-1.5 rounded-full ${accent === 'cyan' ? 'bg-primary' : 'bg-tertiary'}`}></div>
               <div className="flex flex-col">
                 <span className="font-label-sm text-[9px] text-on-surface uppercase tracking-wider">{supportingValue}</span>
                 <span className="font-label-sm text-[9px] text-outline uppercase">{supportingLabel}</span>
               </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default MetricCard;
