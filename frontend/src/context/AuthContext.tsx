import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import {
  UserProfile,
  getAuthToken,
  setAuthToken,
  removeAuthToken,
  loginOperator,
  fetchCurrentUser,
  logoutOperator,
} from '../services/api';

export type AuthState = 'loading' | 'authenticated' | 'unauthenticated';

interface AuthContextType {
  authState: AuthState;
  user: UserProfile | null;
  token: string | null;
  error: string | null;
  login: (username: string, password: string) => Promise<boolean>;
  loginWithGoogle: () => void;
  logout: () => Promise<void>;
  clearError: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [authState, setAuthState] = useState<AuthState>('loading');
  const [user, setUser] = useState<UserProfile | null>(null);
  const [token, setTokenState] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  // Handle OAuth callback parameters and verify existing session on mount
  useEffect(() => {
    const initializeAuth = async () => {
      try {
        const urlParams = new URLSearchParams(window.location.search);
        const urlToken = urlParams.get('auth_token');
        const urlError = urlParams.get('error');
        const urlMessage = urlParams.get('message');

        // Clean query parameters from URL for clean browser history
        if (urlToken || urlError) {
          const cleanPath = window.location.pathname;
          window.history.replaceState({}, document.title, cleanPath);
        }

        if (urlError) {
          if (urlError === 'google_not_configured') {
            setError(
              urlMessage ||
                'Google OAuth is not configured. Please configure GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in the environment.'
            );
          } else if (urlError === 'access_denied') {
            setError('Google sign-in was cancelled by the user.');
          } else if (urlError === 'invalid_oauth_state') {
            setError('OAuth security validation (CSRF state) failed. Please try again.');
          } else {
            setError(`Google authentication failed: ${urlError.replace(/_/g, ' ')}`);
          }
        }

        let candidateToken: string | null = urlToken || getAuthToken();

        if (urlToken) {
          setAuthToken(urlToken);
        }

        if (!candidateToken) {
          setAuthState('unauthenticated');
          return;
        }

        // Verify token with backend
        try {
          const profile = await fetchCurrentUser(candidateToken);
          setUser(profile);
          setTokenState(candidateToken);
          setAuthState('authenticated');
        } catch {
          // Token expired or invalid
          removeAuthToken();
          setUser(null);
          setTokenState(null);
          setAuthState('unauthenticated');
        }
      } catch (err: any) {
        console.error('[V-SHIELD Auth] Initialization error:', err);
        setAuthState('unauthenticated');
      }
    };

    initializeAuth();
  }, []);

  const login = async (username: string, password: string): Promise<boolean> => {
    setError(null);
    try {
      const result = await loginOperator(username, password);
      setUser(result.user);
      setTokenState(result.access_token);
      setAuthState('authenticated');
      return true;
    } catch (err: any) {
      const msg = err?.message || 'Authentication failed. Please verify your credentials.';
      setError(msg);
      return false;
    }
  };

  const loginWithGoogle = () => {
    setError(null);
    // Direct browser redirect to backend Google OAuth initiation endpoint
    window.location.href = '/api/v1/auth/google/login';
  };

  const logout = async () => {
    try {
      await logoutOperator();
    } finally {
      setUser(null);
      setTokenState(null);
      setAuthState('unauthenticated');
      // If currently on any subpath, clear to root
      if (window.location.pathname !== '/' && window.location.pathname !== '/login') {
        window.history.pushState({}, document.title, '/login');
      }
    }
  };

  return (
    <AuthContext.Provider
      value={{
        authState,
        user,
        token,
        error,
        login,
        loginWithGoogle,
        logout,
        clearError,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
