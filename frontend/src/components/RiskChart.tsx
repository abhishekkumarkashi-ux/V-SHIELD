import React from 'react';

interface RiskChartProps {
  history: number[]; // Array of risk scores (0-100)
  maxPoints?: number;
}

const RiskChart: React.FC<RiskChartProps> = ({ history, maxPoints = 60 }) => {
  // Ensure we only show up to maxPoints
  const data = history.slice(-maxPoints);
  
  if (data.length === 0) {
    return (
      <div className="w-full h-48 bg-slate-800/50 rounded-lg flex items-center justify-center border border-slate-700">
        <span className="text-slate-500 text-sm">Waiting for live data...</span>
      </div>
    );
  }

  // Calculate SVG paths
  const width = 1000;
  const height = 200;
  
  const stepX = width / (maxPoints - 1);
  const getX = (index: number) => index * stepX;
  const getY = (value: number) => height - (value / 100) * height;

  const pathD = data.map((val, i) => {
    // Pad left if we don't have enough data points yet
    const xIndex = i + (maxPoints - data.length);
    const x = getX(xIndex);
    const y = getY(val);
    return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
  }).join(' ');

  // Determine line color based on last point
  const currentRisk = data[data.length - 1];
  let strokeColor = '#3b82f6'; // Blue
  if (currentRisk > 79) strokeColor = '#ef4444'; // Red
  else if (currentRisk > 59) strokeColor = '#f97316'; // Orange
  else if (currentRisk > 29) strokeColor = '#eab308'; // Yellow

  return (
    <div className="w-full h-48 bg-slate-900 rounded-lg border border-slate-700 relative overflow-hidden">
      {/* Grid lines */}
      <div className="absolute inset-0 flex flex-col justify-between p-2 opacity-10 pointer-events-none">
         <div className="border-t border-slate-400 w-full"></div>
         <div className="border-t border-slate-400 w-full"></div>
         <div className="border-t border-slate-400 w-full"></div>
         <div className="border-t border-slate-400 w-full"></div>
      </div>
      
      {/* Y-axis labels */}
      <div className="absolute left-2 top-0 bottom-0 py-2 flex flex-col justify-between text-[10px] text-slate-500 font-mono">
        <span>100</span>
        <span>75</span>
        <span>50</span>
        <span>25</span>
        <span>0</span>
      </div>

      <svg 
        viewBox={`0 0 ${width} ${height}`} 
        className="w-full h-full pt-4 pb-4 px-8 preserve-aspect-none"
        preserveAspectRatio="none"
      >
        <path
          d={pathD}
          fill="none"
          stroke={strokeColor}
          strokeWidth="3"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="transition-all duration-300"
        />
        {/* Plot current point */}
        {data.length > 0 && (
          <circle
            cx={getX(maxPoints - 1)}
            cy={getY(currentRisk)}
            r="6"
            fill={strokeColor}
            className="transition-all duration-300 shadow-xl shadow-red-500"
          />
        )}
      </svg>
    </div>
  );
};

export default RiskChart;
