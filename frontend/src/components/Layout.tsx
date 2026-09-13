import { useState, useEffect } from 'react';
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom';
import { Shield, LayoutDashboard, Mic, UserCheck, History, Lock, Settings, User, LogOut } from 'lucide-react';
import { authService, healthService } from '../services/api';

const Layout = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const [backendStatus, setBackendStatus] = useState<'checking' | 'online' | 'offline'>('checking');
  const [user, setUser] = useState<any>(null);

  useEffect(() => {
    // Check health
    healthService.check()
      .then(() => setBackendStatus('online'))
      .catch(() => setBackendStatus('offline'));

    // Fetch user
    authService.getMe()
      .then(u => setUser(u))
      .catch(() => navigate('/login'));
  }, [navigate]);

  const handleLogout = async () => {
    try {
      await authService.logout();
    } catch(e) {}
    navigate('/login');
  };

  const navItems = [
    { name: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
    { name: 'Live Analysis', path: '/live-analysis', icon: Mic },
    { name: 'Speaker Verification', path: '/speaker', icon: UserCheck },
    { name: 'History', path: '/history', icon: History },
    { name: 'Security', path: '/security', icon: Lock },
    { name: 'Settings', path: '/settings', icon: Settings },
  ];

  return (
    <div className="flex h-screen bg-slate-950 text-slate-50 font-sans selection:bg-blue-500/30">
      {/* Sidebar */}
      <div className="w-64 bg-slate-900 border-r border-slate-800 flex flex-col hidden md:flex">
        <div className="p-6 flex items-center gap-3">
          <Shield className="w-8 h-8 text-blue-500" />
          <div>
            <h1 className="text-xl font-bold tracking-tight">V-SHIELD</h1>
            <p className="text-xs text-slate-400">Security Channel</p>
          </div>
        </div>
        
        <nav className="flex-1 px-4 py-4 space-y-1 overflow-y-auto">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors text-sm font-medium ${
                  isActive 
                    ? 'bg-blue-500/10 text-blue-400' 
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                }`}
              >
                <Icon className="w-5 h-5" />
                {item.name}
              </Link>
            );
          })}
        </nav>
        
        <div className="p-4 border-t border-slate-800">
          <Link to="/profile" className="flex items-center gap-3 px-3 py-2 rounded-lg text-slate-400 hover:text-slate-200 transition-colors text-sm font-medium mb-1">
            <User className="w-5 h-5" />
            Profile
          </Link>
          <button onClick={handleLogout} className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-slate-400 hover:text-red-400 transition-colors text-sm font-medium">
            <LogOut className="w-5 h-5" />
            Logout
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col h-screen overflow-hidden">
        {/* Topbar */}
        <header className="h-16 bg-slate-900/50 backdrop-blur-md border-b border-slate-800 flex items-center justify-between px-6 z-10">
          <div className="flex items-center gap-4">
            <h2 className="text-lg font-semibold text-slate-200 capitalize">
              {location.pathname.replace('/', '').replace('-', ' ')}
            </h2>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${
                backendStatus === 'online' ? 'bg-green-500' : 
                backendStatus === 'checking' ? 'bg-yellow-500 animate-pulse' : 'bg-red-500'
              }`} />
              <span className="text-xs text-slate-400">
                {backendStatus === 'online' ? 'System Online' : 
                 backendStatus === 'checking' ? 'Connecting...' : 'Backend Offline'}
              </span>
            </div>
            {user && (
              <div className="flex items-center gap-2 ml-4 pl-4 border-l border-slate-800">
                <span className="text-sm font-medium text-slate-300">{user.name || user.email}</span>
                {user.picture ? (
                  <img src={user.picture} alt="Profile" className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700" />
                ) : (
                  <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center border border-slate-700">
                    <User className="w-4 h-4 text-slate-400" />
                  </div>
                )}
              </div>
            )}
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-y-auto bg-slate-950 p-6 relative">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default Layout;
