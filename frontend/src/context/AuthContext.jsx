/**
 * Authentication Context & Provider
 *
 * Manages user authentication state, handles initial session checking via /auth/me,
 * and exposes actions for logging in via Google OAuth and logging out.
 */

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { authApi } from '../services/authApi.js';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const checkAuth = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await authApi.getMe();
      setUser(data?.user || null);
    } catch (err) {
      if (err.status !== 401) {
        setError(err.message || 'Failed to authenticate session.');
      }
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  const loginWithGoogle = () => {
    authApi.initiateGoogleOAuth();
  };

  const logout = async () => {
    try {
      await authApi.logout();
      setUser(null);
      window.location.href = '/login';
    } catch (err) {
      console.error('Logout error:', err);
      setUser(null);
      window.location.href = '/login';
    }
  };

  const value = {
    user,
    loading,
    error,
    isAuthenticated: Boolean(user),
    checkAuth,
    loginWithGoogle,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
