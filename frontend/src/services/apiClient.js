/**
 * Centralized API Client
 *
 * Enforces:
 * - Decoupled base URL configuration
 * - HttpOnly session cookie credentials ('include')
 * - AbortController timeout handling
 * - Clean error normalization (no exposed stack traces)
 * - Safe JSON parsing
 */

import { getApiBaseUrl } from './apiConfig.js';

const DEFAULT_TIMEOUT_MS = 30000;

export class ApiError extends Error {
  constructor(message, status = 500, code = 'API_ERROR', details = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

/**
 * Perform an authenticated HTTP request
 * @param {string} endpoint
 * @param {RequestInit & { timeout?: number }} [options]
 * @returns {Promise<any>}
 */
export async function request(endpoint, options = {}) {
  const {
    timeout = DEFAULT_TIMEOUT_MS,
    headers = {},
    body,
    ...customConfig
  } = options;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  // Auto-detect JSON vs FormData body
  const isFormData = typeof FormData !== 'undefined' && body instanceof FormData;
  const mergedHeaders = {
    ...(!isFormData ? { 'Content-Type': 'application/json' } : {}),
    Accept: 'application/json',
    ...headers,
  };

  const apiBaseUrl = getApiBaseUrl();
  const url = `${apiBaseUrl}${endpoint}`;

  try {
    const response = await fetch(url, {
      ...customConfig,
      headers: mergedHeaders,
      body: isFormData ? body : (body && typeof body === 'object' ? JSON.stringify(body) : body),
      credentials: 'include', // Secure HttpOnly cookie auth
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    // Parse response
    let responseData = null;
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      try {
        responseData = await response.json();
      } catch {
        responseData = null;
      }
    } else {
      try {
        responseData = await response.text();
      } catch {
        responseData = null;
      }
    }

    if (!response.ok) {
      const status = response.status;
      let friendlyMessage = 'An unexpected server error occurred. Please try again.';
      let errorCode = 'SERVER_ERROR';

      switch (status) {
        case 400:
          friendlyMessage = responseData?.message || 'Invalid request parameters.';
          errorCode = 'BAD_REQUEST';
          break;
        case 401:
          friendlyMessage = 'Authentication required. Please sign in to continue.';
          errorCode = 'UNAUTHORIZED';
          break;
        case 403:
          friendlyMessage = "You don't have permission to view this workout.";
          errorCode = 'FORBIDDEN';
          break;
        case 404:
          friendlyMessage = responseData?.message || 'The requested resource or workout job was not found.';
          errorCode = 'NOT_FOUND';
          break;
        case 409:
          friendlyMessage = responseData?.message || 'A conflicting job is already in progress.';
          errorCode = 'CONFLICT';
          break;
        case 413:
          friendlyMessage = 'The uploaded video payload is too large. Max limit is 100 MB.';
          errorCode = 'PAYLOAD_TOO_LARGE';
          break;
        case 422:
          friendlyMessage = responseData?.detail || responseData?.message || 'Input validation failed.';
          errorCode = 'VALIDATION_ERROR';
          break;
        case 429:
          friendlyMessage = 'Too many requests. Please slow down and try again.';
          errorCode = 'RATE_LIMITED';
          break;
        case 500:
          friendlyMessage = 'The AI analysis engine encountered an unexpected error. Please retry.';
          errorCode = 'INTERNAL_ERROR';
          break;
        case 503:
          friendlyMessage = 'The vision computing cluster is currently undergoing maintenance.';
          errorCode = 'SERVICE_UNAVAILABLE';
          break;
        default:
          friendlyMessage = responseData?.message || `Request failed with status ${status}.`;
          errorCode = `HTTP_${status}`;
      }

      throw new ApiError(friendlyMessage, status, errorCode, responseData);
    }

    return responseData;
  } catch (error) {
    clearTimeout(timeoutId);

    if (error instanceof ApiError) {
      throw error;
    }

    if (error.name === 'AbortError') {
      throw new ApiError('Request timed out while waiting for vision server response.', 408, 'TIMEOUT');
    }

    throw new ApiError('Unable to connect to Workout Form Coach server. Please check your network.', 0, 'NETWORK_ERROR');
  }
}

export const apiClient = {
  get: (endpoint, options) => request(endpoint, { ...options, method: 'GET' }),
  post: (endpoint, body, options) => request(endpoint, { ...options, method: 'POST', body }),
  put: (endpoint, body, options) => request(endpoint, { ...options, method: 'PUT', body }),
  delete: (endpoint, options) => request(endpoint, { ...options, method: 'DELETE' }),
};
