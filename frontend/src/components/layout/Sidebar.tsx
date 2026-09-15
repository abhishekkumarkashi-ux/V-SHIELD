import { Link, useLocation } from 'react-router-dom';
import { 
  Shield, 
  LayoutDashboard, 
  Mic, 
  Activity, 
  UserCheck, 
  ShieldAlert, 
  History, 
  Bell, 
  Cpu, 
  BarChart2, 
  Plug, 
  Settings,
  Circle
} from 'lucide-react';

const Sidebar = ({ user }: { user: any }) => {
  const location = useLocation();

  const operationsNav = [
    { name: 'Overview', path: '/dashboard', icon: LayoutDashboard },
    { name: 'Live Protection', path: '/live-analysis', icon: Mic },
    { name: 'Call Analysis', path: '/call-analysis', icon: Activity },
    { name: 'Voice Verification', path: '/speaker', icon: UserCheck },
    { name: 'Risk Intelligence', path: '/risk-intelligence', icon: ShieldAlert },
    { name: 'Call History', path: '/history', icon: History },
    { name: 'Security Alerts', path: '/security-alerts', icon: Bell },
  ];

  const forensicsNav = [
    { name: 'AI Model Center', path: '/ai-models', icon: Cpu },
    { name: 'Analytics', path: '/analytics', icon: BarChart2 },
    { name: 'Integrations', path: '/integrations', icon: Plug },
    { name: 'Settings', path: '/settings', icon: Settings },
  ];

  const NavGroup = ({ title, items }: { title: string, items: any[] }) => (
    <div className="mb-6">
      <h3 className="px-4 text-[11px] font-label-sm text-outline tracking-wider uppercase mb-2">
        {title}
      </h3>
      <div className="space-y-[2px]">
        {items.map((item) => {
          const Icon = item.icon;
          const isActive = location.pathname.startsWith(item.path);
          return (
            <Link
              key={item.path}
              to={item.path}
              className={`flex items-center gap-3 px-4 py-2 text-sm transition-all border-l-2 ${
                isActive 
                  ? 'bg-primary/10 text-primary border-primary' 
                  : 'text-outline hover:text-on-surface hover:bg-surface-container-high hover:border-outline-variant border-transparent border-dashed'
              }`}
            >
              <Icon className="w-[18px] h-[18px]" />
              <span className="font-medium">{item.name}</span>
            </Link>
          );
        })}
      </div>
    </div>
  );

  return (
    <aside className="w-[200px] h-full flex flex-col bg-surface-container-lowest border-r border-outline-variant shrink-0">
      {/* Header */}
      <div className="p-5 flex items-center gap-3 border-b border-outline-variant">
        <div className="relative">
          <Shield className="w-8 h-8 text-primary" />
          <div className="absolute -bottom-1 -right-1 w-3 h-3 bg-background rounded-full flex items-center justify-center">
            <Circle className="w-2 h-2 text-tertiary fill-tertiary" />
          </div>
        </div>
        <div className="flex flex-col">
          <span className="font-label-sm font-bold text-on-surface tracking-widest text-[13px] leading-tight">V-SHIELD</span>
          <span className="font-label-sm font-medium text-primary text-[10px] tracking-wider">VOICE DEFENSE</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-5 custom-scrollbar">
        <NavGroup title="OPERATIONS" items={operationsNav} />
        <NavGroup title="FORENSICS & INTEL" items={forensicsNav} />
      </nav>

      {/* Telemetry Footer */}
      <div className="p-4 border-t border-outline-variant bg-surface-container-lowest flex flex-col gap-3">
        <div className="flex flex-col gap-1">
          <div className="flex justify-between items-center text-[10px] font-label-sm text-outline">
            <span>TELEMETRY SLA</span>
            <span className="text-tertiary font-bold">99.98%</span>
          </div>
          <div className="flex justify-between items-center text-[10px] font-label-sm text-outline">
            <span>ENGINE PING</span>
            <span className="text-primary font-bold">14ms</span>
          </div>
        </div>
        
        <div className="flex items-center gap-2 pt-3 border-t border-outline-variant/50">
          <div className="w-6 h-6 rounded bg-surface-container-high flex items-center justify-center border border-outline-variant">
            <Shield className="w-3 h-3 text-outline" />
          </div>
          <div className="flex flex-col">
            <span className="text-xs font-bold text-on-surface truncate w-32">{user?.name || user?.email || 'C. Mercer (Lead)'}</span>
            <span className="text-[10px] text-outline">SOC Tier 3</span>
          </div>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
