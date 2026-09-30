/**
 * Workout Jobs & Analysis Service Layer
 *
 * Implements the Workout Form Coach Backend API Specification (v1).
 * Supports both Mock Mode and Live Python API with 2-step video upload & YouTube ingestion.
 */

import { apiClient } from './apiClient.js';
import { ENDPOINTS } from './apiEndpoints.js';
import {
  mockJobsDb,
  MOCK_SQUAT_REPS,
  advanceMockJobProgress,
  insertMockJob,
} from './mockData.js';
import { isMockApiEnabled, getApiBaseUrl } from './apiConfig.js';

const EXERCISE_NAMES = {
  squat: 'Squat',
  pushup: 'Push-up',
  lunge: 'Lunge',
};

export const jobsApi = {
  /**
   * Fetch all workout jobs for the authenticated user
   * Handles backend paginated response { items: [...], total, limit, offset }
   * @returns {Promise<{ jobs: Array<any>, total?: number }>}
   */
  async getJobs() {
    if (isMockApiEnabled()) {
      await new Promise((r) => setTimeout(r, 200));
      return { jobs: [...mockJobsDb], total: mockJobsDb.length };
    }

    const data = await apiClient.get(ENDPOINTS.JOBS);
    const jobsList = data?.items || data?.jobs || (Array.isArray(data) ? data : []);

    const normalizedJobs = jobsList.map((job) => ({
      ...job,
      exercise_name: job.exercise_name || EXERCISE_NAMES[job.exercise] || job.exercise || 'Workout',
    }));

    return {
      jobs: normalizedJobs,
      total: data?.total ?? normalizedJobs.length,
    };
  },

  /**
   * Fetch a single job by its ID
   * @param {string} jobId
   * @returns {Promise<any>}
   */
  async getJob(jobId) {
    if (isMockApiEnabled()) {
      await new Promise((r) => setTimeout(r, 150));
      const job = mockJobsDb.find((j) => j.job_id === jobId);
      if (!job) {
        const error = new Error('Workout job not found.');
        error.status = 404;
        throw error;
      }
      return job;
    }

    const job = await apiClient.get(ENDPOINTS.JOB_DETAILS(jobId));
    return {
      ...job,
      exercise_name: job.exercise_name || EXERCISE_NAMES[job.exercise] || job.exercise || 'Workout',
    };
  },

  /**
   * Submit a new workout job for asynchronous AI analysis
   * Adheres to the documented 2-step ingestion protocol:
   *  Flow A (Direct Upload):
   *    1. POST /api/v1/jobs -> { exercise, source_type: "upload" }
   *    2. POST /api/v1/jobs/{job_id}/video -> FormData with field 'file'
   *  Flow B (YouTube):
   *    1. POST /api/v1/jobs -> { exercise, source_type: "youtube", source_url }
   *    2. POST /api/v1/jobs/{job_id}/youtube -> trigger server-side ingestion
   *
   * @param {{ exercise: string, video?: File, youtube_url?: string }} submission
   * @returns {Promise<{ job_id: string, status: string }>}
   */
  async createJob(submission) {
    const exercise = submission.exercise || 'squat';

    if (isMockApiEnabled()) {
      await new Promise((r) => setTimeout(r, 600));

      const newId = `job_${Date.now().toString(36)}`;
      const newJob = {
        job_id: newId,
        session_num: Math.floor(886 + Math.random() * 50),
        exercise,
        exercise_name: EXERCISE_NAMES[exercise] || 'Workout Analysis',
        source_type: submission.youtube_url ? 'youtube' : 'upload',
        video_filename: submission.video?.name || null,
        youtube_url: submission.youtube_url || null,
        status: 'queued',
        progress: 0,
        created_at: new Date().toISOString(),
        error: null,
        queue_position: 1,
        estimated_wait: '20 seconds',
      };

      insertMockJob(newJob);

      return {
        job_id: newId,
        status: 'queued',
      };
    }

    // Live Python Backend 2-Step Ingestion Flow:
    if (submission.video) {
      // Step 1: Register job
      const jobRecord = await apiClient.post(ENDPOINTS.JOBS, {
        exercise,
        source_type: 'upload',
      });

      const jobId = jobRecord.job_id;

      // Step 2: Upload video file via multipart/form-data with field 'file'
      const formData = new FormData();
      formData.append('file', submission.video);
      await apiClient.post(ENDPOINTS.JOB_VIDEO_UPLOAD(jobId), formData);

      return {
        job_id: jobId,
        status: 'queued',
      };
    } else {
      // Step 1: Register YouTube job
      const jobRecord = await apiClient.post(ENDPOINTS.JOBS, {
        exercise,
        source_type: 'youtube',
        source_url: submission.youtube_url,
      });

      const jobId = jobRecord.job_id;

      // Step 2: Trigger YouTube download ingestion
      await apiClient.post(ENDPOINTS.JOB_YOUTUBE_INGEST(jobId), {});

      return {
        job_id: jobId,
        status: 'queued',
      };
    }
  },

  /**
   * Fetch rep-by-rep kinematic telemetry
   * @param {string} jobId
   * @returns {Promise<{ reps: Array<any>, total_reps?: number }>}
   */
  async getJobReps(jobId) {
    if (isMockApiEnabled()) {
      await new Promise((r) => setTimeout(r, 150));
      return { reps: MOCK_SQUAT_REPS, total_reps: MOCK_SQUAT_REPS.length };
    }
    const data = await apiClient.get(ENDPOINTS.JOB_REPS(jobId));
    const rawReps = Array.isArray(data?.reps) ? data.reps : [];
    const normalizedReps = rawReps.map((r) => {
      const hasIssues = Array.isArray(r.issues) && r.issues.length > 0;
      return {
        ...r,
        // Map backend form_score to UI expected score
        score: r.form_score ?? null,
        // Flagged if there are detected form issues
        is_flagged: hasIssues,
        status_label: hasIssues ? (r.issues[0]?.code || 'FLAGGED') : 'CLEAN',
        // Primary fault label code if issues exist
        fault_label: hasIssues ? (r.issues[0]?.code || 'FLAGGED') : null,
      };
    });

    return {
      reps: normalizedReps,
      total_reps: data?.total_reps ?? normalizedReps.length,
    };
  },

  /**
   * Fetch high-level summary report for a completed job
   * @param {string} jobId
   * @returns {Promise<any>}
   */
  async getJobReport(jobId) {
    if (isMockApiEnabled()) {
      await new Promise((r) => setTimeout(r, 150));
      const job = mockJobsDb.find((j) => j.job_id === jobId);
      return job?.report || null;
    }
    const data = await apiClient.get(ENDPOINTS.JOB_REPORT(jobId));
    if (!data) return null;

    return {
      ...data,
      // Map backend JobReportResponse to UI expected metric names
      form_score: data.average_score ?? null,
      avg_rom: data.average_rom ?? null,
      avg_tempo: data.average_tempo ?? null,
      total_reps: data.total_reps ?? 0,
      summary: data.summary ?? null,
    };
  },

  /**
   * Returns video stream URL or loads it as a Blob URL using credentials
   * @param {string} jobId
   * @param {'processed' | 'original'} [type='processed']
   * @returns {Promise<string|null>}
   */
  async loadJobVideoUrl(jobId, type = 'processed') {
    if (isMockApiEnabled()) {
      // In mock mode, return static or null to use canvas/fallback player
      return null;
    }

    const apiBase = getApiBaseUrl();
    const query = type === 'original' ? '?type=original' : '?type=processed';
    const streamUrl = `${apiBase}${ENDPOINTS.JOB_VIDEO_STREAM(jobId)}${query}`;

    try {
      const response = await fetch(streamUrl, {
        credentials: 'include',
      });
      if (!response.ok) {
        return streamUrl; // Fallback to direct URL if stream not ready
      }
      const blob = await response.blob();
      return URL.createObjectURL(blob);
    } catch {
      return streamUrl;
    }
  },

  /**
   * Refresh job status without calling nonexistent retry endpoints
   * @param {string} jobId
   * @returns {Promise<any>}
   */
  async retryJob(jobId) {
    if (isMockApiEnabled()) {
      await new Promise((r) => setTimeout(r, 400));
      const job = mockJobsDb.find((j) => j.job_id === jobId);
      if (job) {
        job.status = 'processing';
        job.progress = 10;
        job.error = null;
        job.current_step = 'Reading video frames';
      }
      return { job_id: jobId, status: 'processing' };
    }

    // Send retry request to backend to re-queue the job
    return await apiClient.post(ENDPOINTS.JOB_RETRY(jobId), {});
  },

  /**
   * Delete an owned workout job
   * @param {string} jobId
   * @returns {Promise<any>}
   */
  async deleteJob(jobId) {
    if (isMockApiEnabled()) {
      deleteMockJob(jobId);
      return { message: 'Job deleted', job_id: jobId };
    }
    return await apiClient.delete(ENDPOINTS.JOB_DETAILS(jobId));
  },

  /**
   * Development helper to simulate next step in mock mode
   */
  simulateMockTick(jobId) {
    if (isMockApiEnabled()) {
      return advanceMockJobProgress(jobId);
    }
    return null;
  },
};
