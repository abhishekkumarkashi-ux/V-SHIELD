import React from 'react';
import { Shield, Activity, Clock, LayoutDashboard } from 'lucide-react';

interface NavbarProps {
  currentView: string;
  setCurrentView: (view: string) => void;
}

const Navbar: React.FC<NavbarProps> = ({ currentView, setCurrentView }) => {
  return (
    <nav className="bg-slate-900 border-b border-slate-800 p-4">
      <div className="container mx-auto flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Shield className="w-8 h-8 text-blue-500" />
          <span className="text-xl font-bold tracking-wider text-slate-100">V-SHIELD</span>
        </div>
        <div className="flex space-x-6">
          <button
            onClick={() => setCurrentView('dashboard')}
            className={`flex items-center space-x-2 px-3 py-2 rounded-md transition-colors ${
              currentView === 'dashboard' ? 'bg-slate-800 text-blue-400' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`}
          >
            <LayoutDashboard className="w-5 h-5" />
            <span>Dashboard</span>
          </button>
          <button
            onClick={() => setCurrentView('live')}
            className={`flex items-center space-x-2 px-3 py-2 rounded-md transition-colors ${
              currentView === 'live' ? 'bg-slate-800 text-blue-400' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`}
          >
            <Activity className="w-5 h-5" />
            <span>Live Analysis</span>
          </button>
          <button
            onClick={() => setCurrentView('history')}
            className={`flex items-center space-x-2 px-3 py-2 rounded-md transition-colors ${
              currentView === 'history' ? 'bg-slate-800 text-blue-400' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`}
          >
            <Clock className="w-5 h-5" />
            <span>History</span>
          </button>
        </div>
        <div className="flex items-center space-x-2">
          <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse"></div>
          <span className="text-sm text-slate-300">System Online</span>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
