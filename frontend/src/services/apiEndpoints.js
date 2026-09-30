/**
 * Centralized API Endpoints Contract
 *
 * Adheres strictly to the Workout Form Coach Backend API Specification (v1).
 * All endpoints are prefixed with /api/v1 as documented in the backend integration guide.
 */

export const ENDPOINTS = {
  // Liveness & Health
  HEALTH: '/api/v1/health',

  // Authentication & Session
  AUTH_ME: '/api/v1/auth/me',
  AUTH_GOOGLE_LOGIN: '/api/v1/auth/google/login',
  AUTH_GOOGLE_CALLBACK: '/api/v1/auth/google/callback',
  AUTH_LOGOUT: '/api/v1/auth/logout',

  // Workout Job Management
  JOBS: '/api/v1/jobs',
  JOB_DETAILS: (jobId) => `/api/v1/jobs/${encodeURIComponent(jobId)}`,
  JOB_VIDEO_UPLOAD: (jobId) => `/api/v1/jobs/${encodeURIComponent(jobId)}/video`,
  JOB_YOUTUBE_INGEST: (jobId) => `/api/v1/jobs/${encodeURIComponent(jobId)}/youtube`,
  JOB_RETRY: (jobId) => `/api/v1/jobs/${encodeURIComponent(jobId)}/retry`,

  // Workout Results & Media
  JOB_REPS: (jobId) => `/api/v1/jobs/${encodeURIComponent(jobId)}/reps`,
  JOB_REPORT: (jobId) => `/api/v1/jobs/${encodeURIComponent(jobId)}/report`,
  JOB_VIDEO_STREAM: (jobId) => `/api/v1/jobs/${encodeURIComponent(jobId)}/video`,
};

