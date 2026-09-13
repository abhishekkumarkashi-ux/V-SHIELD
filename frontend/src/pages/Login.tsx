import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { GoogleLogin } from '@react-oauth/google';
import { Shield, Lock, Activity, ShieldCheck } from 'lucide-react';
import { authService } from '../services/api';

const Login = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleGoogleSuccess = async (credentialResponse: any) => {
    try {
      setLoading(true);
      setError('');
      await authService.googleLogin(credentialResponse.credential);
      navigate('/dashboard');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Authentication failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleMockLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      // In a real app this would be a proper email/password flow
      // For this phase, if they use the form, we'll try to bypass for dev if backend allows it
      await authService.googleLogin('mock_dev_token');
      navigate('/dashboard');
    } catch (err: any) {
      setError('Email login requires Google OAuth for now, or use dev token.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex bg-slate-950 font-sans selection:bg-blue-500/30">
      
      {/* LEFT SIDE - Branding */}
      <div className="hidden lg:flex w-1/2 relative bg-slate-900 border-r border-slate-800 items-center justify-center p-12 overflow-hidden">
        {/* Background Gradients */}
        <div className="absolute top-[-10%] left-[-10%] w-96 h-96 bg-blue-600/20 rounded-full blur-[100px]"></div>
        <div className="absolute bottom-[-10%] right-[-10%] w-96 h-96 bg-indigo-600/20 rounded-full blur-[100px]"></div>
        
        <div className="relative z-10 max-w-lg text-slate-100">
          <div className="flex items-center gap-4 mb-8">
            <div className="p-3 bg-blue-500/10 rounded-xl border border-blue-500/20">
              <Shield className="w-10 h-10 text-blue-500" />
            </div>
            <h1 className="text-4xl font-bold tracking-tight">V-SHIELD</h1>
          </div>
          
          <h2 className="text-3xl font-bold mb-6 leading-tight bg-gradient-to-br from-white to-slate-400 bg-clip-text text-transparent">
            Turning voice communication into a verified security channel.
          </h2>
          
          <p className="text-slate-400 text-lg mb-12">
            The industry's leading real-time anti-spoofing and speaker verification engine. 
            Protect your sensitive communications against synthetic voice and impersonation attacks.
          </p>

          <div className="space-y-6">
            <div className="flex items-start gap-4">
              <div className="p-2 bg-slate-800/50 rounded-lg border border-slate-700/50 mt-1">
                <Activity className="w-5 h-5 text-indigo-400" />
              </div>
              <div>
                <h3 className="font-semibold text-slate-200">Real-Time Risk Analysis</h3>
                <p className="text-sm text-slate-400 mt-1">Detect AI-generated voices with sub-second latency.</p>
              </div>
            </div>
            <div className="flex items-start gap-4">
              <div className="p-2 bg-slate-800/50 rounded-lg border border-slate-700/50 mt-1">
                <ShieldCheck className="w-5 h-5 text-emerald-400" />
              </div>
              <div>
                <h3 className="font-semibold text-slate-200">Continuous Identity Verification</h3>
                <p className="text-sm text-slate-400 mt-1">Ensure the person speaking is exactly who they claim to be.</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* RIGHT SIDE - Auth */}
      <div className="w-full lg:w-1/2 flex items-center justify-center p-8 sm:p-12">
        <div className="w-full max-w-md space-y-8">
          <div className="text-center lg:text-left">
            <div className="lg:hidden flex items-center justify-center gap-3 mb-6">
              <Shield className="w-8 h-8 text-blue-500" />
              <h1 className="text-2xl font-bold tracking-tight text-white">V-SHIELD</h1>
            </div>
            <h2 className="text-3xl font-bold text-slate-100 tracking-tight">Welcome back</h2>
            <p className="text-slate-400 mt-2 text-sm">Sign in to your security dashboard</p>
          </div>

          <div className="bg-slate-900 border border-slate-800 p-8 rounded-2xl shadow-xl shadow-black/50 relative overflow-hidden">
            <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-blue-500 to-indigo-500"></div>
            
            <form onSubmit={handleMockLogin} className="space-y-5">
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">Email address</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <User className="h-5 w-5 text-slate-500" />
                  </div>
                  <input 
                    type="email" 
                    placeholder="name@company.com" 
                    className="w-full pl-10 pr-4 py-2.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all outline-none placeholder:text-slate-600"
                  />
                </div>
              </div>
              
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="block text-sm font-medium text-slate-400">Password</label>
                  <a href="#" className="text-xs text-blue-400 hover:text-blue-300 transition-colors">Forgot password?</a>
                </div>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <Lock className="h-5 w-5 text-slate-500" />
                  </div>
                  <input 
                    type="password" 
                    placeholder="••••••••" 
                    className="w-full pl-10 pr-4 py-2.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all outline-none placeholder:text-slate-600"
                  />
                </div>
              </div>

              {error && (
                <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                  {error}
                </div>
              )}

              <button 
                disabled={loading}
                type="submit" 
                className="w-full bg-blue-600 hover:bg-blue-500 text-white font-medium py-2.5 rounded-lg transition-colors shadow-lg shadow-blue-500/20 disabled:opacity-50 flex justify-center items-center h-[44px]"
              >
                {loading ? 'Signing in...' : 'Sign In'}
              </button>
            </form>

            <div className="mt-8 flex items-center gap-4">
              <div className="flex-1 h-px bg-slate-800"></div>
              <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">OR</span>
              <div className="flex-1 h-px bg-slate-800"></div>
            </div>

            <div className="mt-8 flex justify-center">
              <GoogleLogin
                onSuccess={handleGoogleSuccess}
                onError={() => setError('Google Sign-In failed.')}
                useOneTap
                theme="filled_black"
                shape="rectangular"
                size="large"
                text="continue_with"
                width="100%"
              />
            </div>
            
            <p className="mt-8 text-center text-sm text-slate-500">
              Don't have an account? <a href="#" className="text-blue-400 hover:text-blue-300 font-medium">Request access</a>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

// Add missing lucide icon import for User in the file
import { User } from 'lucide-react';

export default Login;
