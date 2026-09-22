import React, { useState } from 'react';
import {
  Shield,
  Lock,
  Mail,
  Eye,
  EyeOff,
  AlertTriangle,
  Loader2,
  Info,
  X,
  Sparkles,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export const LoginPage: React.FC = () => {
  const { login, loginWithGoogle, error: authError, clearError } = useAuth();

  const [username, setUsername] = useState('analyst@vshield.internal');
  const [password, setPassword] = useState('VShieldDev2026!');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [showForgotNotice, setShowForgotNotice] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    clearError();
    setLocalError(null);

    if (!username.trim()) {
      setLocalError('Please enter your operator username or email address.');
      return;
    }
    if (!password) {
      setLocalError('Please enter your security access password.');
      return;
    }

    setIsSubmitting(true);
    try {
      const success = await login(username.trim(), password);
      if (!success) {
        setIsSubmitting(false);
      }
    } catch {
      setIsSubmitting(false);
    }
  };

  const activeError = localError || authError;

  return (
    <div className="min-h-screen bg-[#070b14] text-slate-100 flex flex-col justify-center items-center px-4 relative overflow-hidden select-none">
      {/* Ambient background glow elements */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-96 h-96 bg-cyan-600/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute -bottom-20 right-10 w-80 h-80 bg-blue-600/10 rounded-full blur-3xl pointer-events-none" />

      {/* Login Card */}
      <div className="w-full max-w-md z-10">
        {/* Brand Header */}
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center p-3 bg-gradient-to-tr from-cyan-600 to-blue-600 rounded-2xl shadow-xl shadow-cyan-900/40 mb-3 border border-cyan-400/20">
            <Shield className="w-8 h-8 text-white animate-pulse-slow" />
          </div>
          <div className="flex items-center justify-center space-x-2">
            <h1 className="text-2xl font-black tracking-tight text-white">V-SHIELD</h1>
            <span className="text-[11px] font-mono font-bold bg-cyan-950/80 text-cyan-400 border border-cyan-500/40 px-2 py-0.5 rounded-md">
              SIH 2026 #26104
            </span>
          </div>
          <h2 className="text-lg font-bold text-slate-200 mt-2">Welcome back</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Sign in to access V-SHIELD security intelligence.
          </p>
        </div>

        {/* Main Panel */}
        <div className="glass-panel-glow bg-[#0d1322]/90 border border-slate-700/60 rounded-2xl p-6 sm:p-8 shadow-2xl backdrop-blur-xl">
          {/* Error Message Alert */}
          {activeError && (
            <div className="mb-5 bg-red-950/80 border border-red-500/40 text-red-200 text-xs px-3.5 py-2.5 rounded-xl flex items-start justify-between shadow-lg animate-fadeIn">
              <div className="flex items-start space-x-2">
                <AlertTriangle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                <span className="font-medium leading-relaxed">{activeError}</span>
              </div>
              <button
                type="button"
                onClick={() => {
                  setLocalError(null);
                  clearError();
                }}
                className="text-red-400 hover:text-red-200 p-0.5 transition"
                aria-label="Dismiss error"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          {/* Forgot Password Security Notice */}
          {showForgotNotice && (
            <div className="mb-5 bg-cyan-950/80 border border-cyan-500/40 text-cyan-200 text-xs px-3.5 py-2.5 rounded-xl flex items-start justify-between shadow-lg">
              <div className="flex items-start space-x-2">
                <Info className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
                <span>
                  For defense-in-depth compliance, passwords cannot be reset self-service. Please
                  contact your authorized Security Operations Center (SOC) administrator.
                </span>
              </div>
              <button
                type="button"
                onClick={() => setShowForgotNotice(false)}
                className="text-cyan-400 hover:text-cyan-200 p-0.5 transition"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          {/* Email / Password Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Username / Email Field */}
            <div>
              <label
                htmlFor="username"
                className="block text-xs font-semibold text-slate-300 mb-1.5 uppercase tracking-wider"
              >
                Operator Email / Username
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                  <Mail className="w-4 h-4" />
                </div>
                <input
                  id="username"
                  name="username"
                  type="text"
                  autoComplete="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  disabled={isSubmitting}
                  placeholder="analyst@vshield.internal"
                  className="w-full bg-[#070b14]/90 border border-slate-700/80 focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 text-slate-100 placeholder-slate-500 text-sm rounded-xl pl-10 pr-3.5 py-2.5 outline-none transition disabled:opacity-50"
                  required
                />
              </div>
            </div>

            {/* Password Field */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label
                  htmlFor="password"
                  className="block text-xs font-semibold text-slate-300 uppercase tracking-wider"
                >
                  Password
                </label>
                <button
                  type="button"
                  onClick={() => setShowForgotNotice(true)}
                  className="text-xs text-cyan-400 hover:text-cyan-300 hover:underline transition font-medium"
                >
                  Forgot password?
                </button>
              </div>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                  <Lock className="w-4 h-4" />
                </div>
                <input
                  id="password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={isSubmitting}
                  placeholder="••••••••••••"
                  className="w-full bg-[#070b14]/90 border border-slate-700/80 focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 text-slate-100 placeholder-slate-500 text-sm rounded-xl pl-10 pr-11 py-2.5 outline-none transition disabled:opacity-50"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-400 hover:text-slate-200 transition"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* Remember Me Option */}
            <div className="flex items-center">
              <input
                id="remember-me"
                name="remember-me"
                type="checkbox"
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
                className="w-4 h-4 rounded bg-[#070b14] border-slate-700 text-cyan-600 focus:ring-cyan-500 focus:ring-offset-0 focus:ring-1 cursor-pointer"
              />
              <label
                htmlFor="remember-me"
                className="ml-2 block text-xs text-slate-300 cursor-pointer select-none"
              >
                Remember me on this console
              </label>
            </div>

            {/* Primary Sign In Button */}
            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full mt-2 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-bold text-sm py-2.5 px-4 rounded-xl shadow-lg shadow-cyan-900/30 border border-cyan-400/30 transition duration-150 flex items-center justify-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin text-white" />
                  <span>Verifying Credentials...</span>
                </>
              ) : (
                <span>Sign In</span>
              )}
            </button>
          </form>

          {/* Divider */}
          <div className="relative my-5">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-slate-800" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-[#0d1322] px-3 text-slate-500 font-mono tracking-widest font-semibold">
                OR
              </span>
            </div>
          </div>

          {/* Google OAuth Button */}
          <button
            type="button"
            onClick={loginWithGoogle}
            disabled={isSubmitting}
            className="w-full bg-[#111a30]/80 hover:bg-[#1a2747] border border-slate-700/80 hover:border-slate-600 text-slate-200 font-semibold text-xs py-2.5 px-4 rounded-xl transition flex items-center justify-center space-x-3 shadow-md hover:shadow-cyan-950/30 disabled:opacity-50 cursor-pointer"
          >
            {/* Official Google multicolored G SVG */}
            <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24">
              <path
                fill="#4285F4"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              />
              <path
                fill="#34A853"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              />
              <path
                fill="#FBBC05"
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
              />
              <path
                fill="#EA4335"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
              />
            </svg>
            <span>Continue with Google</span>
          </button>

          {/* Development Default Credentials Hint */}
          <div className="mt-5 p-2.5 bg-slate-900/60 border border-slate-800/80 rounded-xl text-[11px] font-mono text-slate-400 flex items-start space-x-2">
            <Sparkles className="w-3.5 h-3.5 text-cyan-400 shrink-0 mt-0.5" />
            <div>
              <span className="text-slate-300 font-semibold">Demo Operator: </span>
              <span className="text-cyan-400">analyst@vshield.internal</span>
              <span className="text-slate-500"> / </span>
              <span className="text-cyan-400">VShieldDev2026!</span>
            </div>
          </div>
        </div>

        {/* Footer info */}
        <p className="text-center text-[11px] font-mono text-slate-500 mt-5">
          V-SHIELD • Voice Impersonation Defense & Fraud Prevention Platform
        </p>
      </div>
    </div>
  );
};
