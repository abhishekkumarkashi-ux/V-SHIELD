import { useState, useEffect } from 'react';
import { User, Mail, ShieldCheck } from 'lucide-react';
import { authService } from '../services/api';

const Profile = () => {
  const [user, setUser] = useState<any>(null);

  useEffect(() => {
    authService.getMe().then(setUser).catch(() => {});
  }, []);

  if (!user) return <div className="text-slate-400 animate-pulse">Loading profile...</div>;

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
        <div className="h-32 bg-gradient-to-r from-blue-600/20 to-indigo-600/20 border-b border-slate-800"></div>
        <div className="p-6 relative">
          <div className="absolute -top-12 border-4 border-slate-900 rounded-full bg-slate-800 p-1">
            {user.picture ? (
              <img src={user.picture} alt="Avatar" className="w-20 h-20 rounded-full" />
            ) : (
              <div className="w-20 h-20 rounded-full bg-slate-700 flex items-center justify-center">
                <User className="w-10 h-10 text-slate-400" />
              </div>
            )}
          </div>
          
          <div className="mt-12">
            <h2 className="text-2xl font-bold text-slate-100">{user.name || 'User'}</h2>
            <div className="flex items-center gap-2 text-slate-400 mt-1">
              <Mail className="w-4 h-4" />
              <span>{user.email}</span>
            </div>
            
            <div className="mt-6 inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-sm font-medium">
              <ShieldCheck className="w-4 h-4" />
              Authenticated via Google
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Profile;
