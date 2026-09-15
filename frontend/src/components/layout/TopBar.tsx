import { Search, Bell, HelpCircle, User, CheckCircle2, ChevronDown } from 'lucide-react';

const TopBar = ({ user, backendStatus }: { user: any, backendStatus: string }) => {
  return (
    <header className="h-[60px] bg-surface-container border-b border-outline-variant flex items-center justify-between px-6 shrink-0 z-10">
      {/* Left: Breadcrumbs & Status */}
      <div className="flex items-center gap-4">
        <div className="flex items-center text-[11px] font-label-sm font-bold tracking-widest text-outline uppercase">
          <span className="text-on-surface">V-SHIELD</span>
          <span className="mx-2 text-outline-variant">/</span>
          <span className="text-primary">DEFENSE CONSOLE</span>
        </div>
        
        <div className="h-4 w-[1px] bg-outline-variant mx-2" />
        
        <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-surface-container-highest border border-outline-variant">
          {backendStatus === 'online' ? (
            <CheckCircle2 className="w-3.5 h-3.5 text-tertiary" />
          ) : (
            <div className={`w-2 h-2 rounded-full ${backendStatus === 'checking' ? 'bg-yellow-500 animate-pulse' : 'bg-error'}`} />
          )}
          <span className={`text-[10px] font-label-sm uppercase font-bold tracking-wider ${backendStatus === 'online' ? 'text-tertiary' : 'text-outline'}`}>
            {backendStatus === 'online' ? 'ALL SYSTEMS OPERATIONAL' : backendStatus === 'checking' ? 'CONNECTING...' : 'SYSTEM OFFLINE'}
          </span>
        </div>
      </div>

      {/* Right: Search & Actions */}
      <div className="flex items-center gap-4">
        {/* Search */}
        <div className="relative group">
          <Search className="w-4 h-4 text-outline absolute left-3 top-1/2 -translate-y-1/2 group-focus-within:text-primary transition-colors" />
          <input 
            type="text" 
            placeholder="Search calls, threat hashes, callers" 
            className="bg-surface-container-highest border border-outline-variant rounded px-9 py-1.5 text-xs text-on-surface w-[300px] focus:outline-none focus:border-primary/50 transition-colors placeholder:text-outline"
          />
          <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-0.5 opacity-50">
            <kbd className="font-label-sm text-[10px] bg-surface-container px-1 rounded border border-outline-variant">⌘</kbd>
            <kbd className="font-label-sm text-[10px] bg-surface-container px-1 rounded border border-outline-variant">K</kbd>
          </div>
        </div>

        {/* Environment Selector */}
        <button className="flex items-center gap-2 px-3 py-1.5 rounded bg-surface-container-highest border border-outline-variant hover:bg-surface-container-low transition-colors">
          <div className="flex flex-col text-left">
            <span className="text-[11px] font-medium text-on-surface leading-tight">Enterprise SOC - US</span>
            <span className="text-[10px] text-outline leading-tight">East</span>
          </div>
          <ChevronDown className="w-4 h-4 text-outline" />
        </button>

        <div className="h-6 w-[1px] bg-outline-variant mx-1" />

        {/* Actions */}
        <div className="flex items-center gap-2">
          <button className="p-1.5 rounded text-outline hover:text-on-surface hover:bg-surface-container-highest transition-colors relative">
            <Bell className="w-4 h-4" />
            <span className="absolute top-1 right-1 w-1.5 h-1.5 bg-error rounded-full" />
          </button>
          <button className="p-1.5 rounded text-outline hover:text-on-surface hover:bg-surface-container-highest transition-colors">
            <HelpCircle className="w-4 h-4" />
          </button>
          
          <button className="ml-2 w-7 h-7 rounded-full bg-surface-container-highest border border-outline-variant flex items-center justify-center hover:border-primary/50 transition-colors overflow-hidden">
            {user?.picture ? (
              <img src={user.picture} alt="Profile" className="w-full h-full object-cover" />
            ) : (
              <User className="w-4 h-4 text-outline" />
            )}
          </button>
        </div>
      </div>
    </header>
  );
};

export default TopBar;
