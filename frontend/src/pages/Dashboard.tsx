import { Link } from 'react-router-dom';
import { Activity, ShieldCheck, AlertTriangle, ArrowRight } from 'lucide-react';

const Dashboard = () => {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* HERO RISK CARD */}
        <div className="lg:col-span-2 bg-gradient-to-br from-slate-900 to-slate-950 border border-slate-800 rounded-2xl p-8 relative overflow-hidden shadow-2xl min-h-[400px]">
          <div className="absolute top-0 right-0 w-64 h-64 bg-blue-500/10 rounded-full blur-[80px]"></div>
          
          <div className="relative z-10 flex flex-col h-full justify-between">
            <div>
              <h2 className="text-sm font-bold tracking-widest text-slate-400 uppercase mb-8">System Status Overview</h2>
              <div className="flex items-end gap-4 mb-4">
                <span className="text-7xl font-light text-slate-100 tracking-tighter">--</span>
                <span className="text-xl text-slate-500 mb-2">/ 100</span>
              </div>
              
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-800 border border-slate-700 text-slate-400 font-medium tracking-wide mb-8">
                WAITING FOR LIVE SESSION
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex items-center gap-3 text-slate-300">
                <div className="w-2 h-2 rounded-full bg-slate-500 animate-pulse"></div>
                <span>Connect to live analysis to see real-time risk scores.</span>
              </div>
              
              <div className="grid grid-cols-2 gap-4 pt-6 border-t border-slate-800/50">
                <div>
                  <div className="text-slate-500 text-sm mb-1">Spoof Probability</div>
                  <div className="text-xl font-medium text-slate-200">-- %</div>
                </div>
                <div>
                  <div className="text-slate-500 text-sm mb-1">Speaker Similarity</div>
                  <div className="text-xl font-medium text-slate-200">-- %</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* QUICK ACTIONS */}
        <div className="space-y-6 flex flex-col">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
            <h3 className="font-medium text-slate-200 mb-4">Quick Actions</h3>
            <div className="space-y-3">
              <Link to="/live-analysis" className="w-full flex items-center justify-between p-4 rounded-xl bg-blue-600 hover:bg-blue-500 transition-colors group shadow-lg shadow-blue-500/20">
                <div className="flex items-center gap-3 text-white">
                  <Activity className="w-5 h-5" />
                  <span className="font-medium">Start Live Analysis</span>
                </div>
                <ArrowRight className="w-5 h-5 text-white/70 group-hover:text-white transition-colors" />
              </Link>
              
              <Link to="/speaker" className="w-full flex items-center justify-between p-4 rounded-xl bg-slate-800 hover:bg-slate-700 transition-colors border border-slate-700 group">
                <div className="flex items-center gap-3 text-slate-200">
                  <ShieldCheck className="w-5 h-5 text-emerald-400" />
                  <span className="font-medium">Manage Identity</span>
                </div>
                <ArrowRight className="w-5 h-5 text-slate-400 group-hover:text-slate-200 transition-colors" />
              </Link>
            </div>
          </div>
          
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl flex-1 flex flex-col">
            <h3 className="font-medium text-slate-200 mb-4">Recent Alerts</h3>
            <div className="flex-1 flex flex-col items-center justify-center text-center">
              <div className="p-3 bg-slate-800 rounded-full mb-3">
                <AlertTriangle className="w-6 h-6 text-slate-500" />
              </div>
              <p className="text-sm text-slate-400">No recent security alerts</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
