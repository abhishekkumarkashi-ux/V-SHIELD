import { History as HistoryIcon } from 'lucide-react';

const History = () => {
  return (
    <div className="space-y-6 max-w-4xl">
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 text-center flex flex-col items-center justify-center min-h-[400px]">
        <div className="w-16 h-16 bg-slate-800 rounded-full flex items-center justify-center mb-4">
          <HistoryIcon className="w-8 h-8 text-slate-500" />
        </div>
        <h3 className="text-xl font-medium text-slate-200 mb-2">No analysis history available.</h3>
        <p className="text-slate-400 max-w-md">
          Your historical voice verification and anti-spoofing events will appear here once you start using the live analysis engine.
        </p>
      </div>
    </div>
  );
};

export default History;
