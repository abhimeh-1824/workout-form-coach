/**
 * Authentication Service Abstraction
 *
 * Implements Google OAuth 2.0 with PKCE and server-signed HttpOnly session cookies.
 * Matches Workout Form Coach Backend API Specification (v1).
 */

import { apiClient } from './apiClient.js';
import { ENDPOINTS } from './apiEndpoints.js';
import { MOCK_USER } from './mockData.js';
import {
  createPKCEChallenge,
  generateOAuthState,
  storePKCESession,
  getStoredPKCESession,
  clearPKCESession,
} from '../utils/pkce.js';
import { isMockApiEnabled, getApiBaseUrl } from './apiConfig.js';

export const authApi = {
  /**
   * Get current authenticated athlete profile
   * Sends session_token cookie automatically via credentials: 'include'.
   * @returns {Promise<{ user: any }>}
   */
  async getMe() {
    if (isMockApiEnabled()) {
      const isLoggedOut = sessionStorage.getItem('mock_logged_out') === 'true';
      if (isLoggedOut) {
        return { user: null };
      }
      return { user: MOCK_USER };
    }

    try {
      const data = await apiClient.get(ENDPOINTS.AUTH_ME);
      // Backend returns either { id, email, name, created_at } or { user: {...} }
      const userObj = data?.user || (data?.email ? data : null);
      return { user: userObj };
    } catch (err) {
      if (err.status === 401) {
        return { user: null };
      }
      throw err;
    }
  },

  /**
   * Initiates Google OAuth with PKCE
   * Navigates to /api/v1/auth/google/login as defined in backend documentation.
   */
  async initiateGoogleOAuth() {
    if (isMockApiEnabled()) {
      sessionStorage.removeItem('mock_logged_out');
      // In mock mode, simulate immediate successful login redirect
      window.location.href = '/dashboard';
      return;
    }

    const apiBase = getApiBaseUrl();
    // Redirect browser to backend OAuth login endpoint.
    // The backend generates server-side PKCE challenge & state and redirects to Google.
    window.location.href = `${apiBase}${ENDPOINTS.AUTH_GOOGLE_LOGIN}`;
  },

  /**
   * Verify session upon returning from OAuth redirect
   * @param {{ code?: string, state?: string }} [callbackParams]
   * @returns {Promise<any>}
   */
  async exchangeCodeForToken() {
    clearPKCESession();
    if (isMockApiEnabled()) {
      sessionStorage.removeItem('mock_logged_out');
      return { success: true, user: MOCK_USER };
    }

    // In the backend flow, Google redirects directly to GET /api/v1/auth/google/callback,
    // which sets the HttpOnly session cookie and redirects to FRONTEND_URL.
    // We simply verify authentication status:
    return await this.getMe();
  },

  /**
   * Sign out current user session
   * Calls POST /api/v1/auth/logout to invalidate the HttpOnly cookie.
   */
  async logout() {
    if (isMockApiEnabled()) {
      sessionStorage.setItem('mock_logged_out', 'true');
      return { success: true };
    }

    return await apiClient.post(ENDPOINTS.AUTH_LOGOUT, {});
  },
};
