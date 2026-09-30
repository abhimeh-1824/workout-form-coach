/**
 * API Configuration & Dynamic Backend Switcher
 *
 * Allows switching between Mock API and Live Python API (e.g., FastAPI/Flask)
 * either via .env variables (VITE_API_BASE_URL, VITE_USE_MOCK_API)
 * or dynamically at runtime via localStorage.
 */

const STORAGE_KEY_BASE_URL = 'wfc_api_base_url';
const STORAGE_KEY_USE_MOCK = 'wfc_use_mock_api';

function cleanApiRoot(url) {
  if (!url) return 'http://localhost:8000';
  let cleaned = url.trim().replace(/\/+$/, '');
  // If the user appended /api/v1, strip it so endpoints with /api/v1 don't double-prefix
  cleaned = cleaned.replace(/\/api\/v1\/?$/, '');
  return cleaned.replace(/\/+$/, '');
}

/**
 * Default API Base URL from .env or fallback
 */
export const DEFAULT_ENV_API_URL = cleanApiRoot(import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000');

/**
 * Default mock setting from .env
 */
export const DEFAULT_ENV_USE_MOCK = import.meta.env.VITE_USE_MOCK_API === 'true';

/**
 * Gets the active API Base URL (root host, e.g. http://localhost:8000)
 * @returns {string}
 */
export function getApiBaseUrl() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY_BASE_URL);
    if (saved && saved.trim()) {
      return cleanApiRoot(saved);
    }
  } catch {
    // Ignore storage error
  }
  return DEFAULT_ENV_API_URL;
}

/**
 * Sets a custom API Base URL (e.g. your Python server at http://localhost:8000 or production URL)
 * @param {string} url
 */
export function setApiBaseUrl(url) {
  try {
    if (url && url.trim()) {
      localStorage.setItem(STORAGE_KEY_BASE_URL, cleanApiRoot(url));
    } else {
      localStorage.removeItem(STORAGE_KEY_BASE_URL);
    }
  } catch (err) {
    console.warn('Failed to save API base URL to localStorage:', err);
  }
}

/**
 * Checks if Mock API mode is active
 * @returns {boolean}
 */
export function isMockApiEnabled() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY_USE_MOCK);
    if (saved !== null) {
      return saved === 'true';
    }
  } catch {
    // Ignore storage error
  }
  return DEFAULT_ENV_USE_MOCK;
}

/**
 * Sets whether Mock API mode is enabled
 * @param {boolean} enabled
 */
export function setMockApiEnabled(enabled) {
  try {
    localStorage.setItem(STORAGE_KEY_USE_MOCK, String(enabled));
  } catch (err) {
    console.warn('Failed to save Mock API preference:', err);
  }
}

/**
 * Tests connection to Python API /api/v1/health endpoint
 * @param {string} [customUrl]
 * @returns {Promise<{ ok: boolean, status: number, data?: any, error?: string, latencyMs: number }>}
 */
export async function testBackendConnection(customUrl) {
  const targetBase = cleanApiRoot(customUrl || getApiBaseUrl());
  const healthUrl = `${targetBase}/api/v1/health`;
  const fallbackUrl = `${targetBase}/health`;
  const startTime = performance.now();

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 6000);

    let response = await fetch(healthUrl, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      signal: controller.signal,
    }).catch(() => null);

    // Fallback if /api/v1 prefix not found
    if (!response || response.status === 404) {
      response = await fetch(fallbackUrl, {
        method: 'GET',
        headers: { Accept: 'application/json' },
        signal: controller.signal,
      }).catch(() => null);
    }

    clearTimeout(timeoutId);

    const latencyMs = Math.round(performance.now() - startTime);

    if (response && response.ok) {
      let data = null;
      try {
        data = await response.json();
      } catch {
        data = { status: 'ok' };
      }
      return { ok: true, status: response.status, data, latencyMs };
    }

    if (response) {
      return {
        ok: false,
        status: response.status,
        error: `Server responded with HTTP ${response.status}`,
        latencyMs,
      };
    }

    return {
      ok: false,
      status: 0,
      error: 'Unable to reach backend server',
      latencyMs,
    };
  } catch (err) {
    const latencyMs = Math.round(performance.now() - startTime);
    return {
      ok: false,
      status: 0,
      error: err.name === 'AbortError' ? 'Connection timed out (6s)' : (err.message || 'Network error / server unreachable'),
      latencyMs,
    };
  }
}
