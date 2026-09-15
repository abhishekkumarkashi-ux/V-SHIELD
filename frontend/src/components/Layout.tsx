import { useState, useEffect } from 'react';
import { Outlet, useNavigate } from 'react-router-dom';
import Sidebar from './layout/Sidebar';
import TopBar from './layout/TopBar';
import { authService, healthService } from '../services/api';

const Layout = () => {
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

  return (
    <div className="flex h-screen bg-surface-container-low text-on-background font-sans selection:bg-primary/30 overflow-hidden">
      {/* Sidebar - Fixed left */}
      <Sidebar user={user} />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col h-full overflow-hidden relative z-0">
        {/* Top Command Bar */}
        <TopBar user={user} backendStatus={backendStatus} />

        {/* Page Content */}
        <main className="flex-1 overflow-y-auto bg-background p-6 relative">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default Layout;

