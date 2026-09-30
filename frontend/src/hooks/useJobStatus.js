/**
 * useJobStatus Hook
 *
 * Implements configurable polling for an asynchronous workout analysis job.
 * Only polls while job status is 'queued' or 'processing'.
 * Cleanly cancels intervals on unmount or status resolution.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { jobsApi } from '../services/jobsApi.js';
import { JOB_STATUSES } from '../utils/constants.js';

const DEFAULT_POLL_INTERVAL = 3000; // 3 seconds

export function useJobStatus(jobId, options = {}) {
  const { pollInterval = DEFAULT_POLL_INTERVAL, autoFetchDetails = true } = options;

  const [job, setJob] = useState(null);
  const [reps, setReps] = useState([]);
  const [report, setReport] = useState(null);
  const [videoUrl, setVideoUrl] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isRetrying, setIsRetrying] = useState(false);

  const timerRef = useRef(null);
  const isMountedRef = useRef(true);

  const stopPolling = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const fetchJobData = useCallback(async () => {
    if (!jobId) return;

    try {
      // In mock mode, advance progress on tick if queued/processing
      jobsApi.simulateMockTick(jobId);

      const jobData = await jobsApi.getJob(jobId);

      if (!isMountedRef.current) return;
      setJob(jobData);
      setError(null);

      // If finished, load reps, report, and video stream
      if (jobData.status === JOB_STATUSES.COMPLETED) {
        stopPolling();
        if (autoFetchDetails) {
          try {
            const [repsData, reportData, loadedVideo] = await Promise.all([
              jobsApi.getJobReps(jobId),
              jobsApi.getJobReport(jobId),
              jobsApi.loadJobVideoUrl(jobId),
            ]);
            if (isMountedRef.current) {
              const repsList = repsData?.reps || [];
              const cleanCount = repsList.filter((r) => !r.is_flagged).length;
              const flaggedCount = repsList.filter((r) => r.is_flagged).length;

              const enrichedReport = reportData
                ? {
                    ...reportData,
                    clean_reps: cleanCount,
                    flagged_reps: flaggedCount,
                  }
                : jobData.report || null;

              setReps(repsList);
              setReport(enrichedReport);
              if (loadedVideo) setVideoUrl(loadedVideo);
            }
          } catch (err) {
            console.error('Failed fetching finished job telemetry:', err);
          }
        }
      } else if (jobData.status === JOB_STATUSES.FAILED) {
        stopPolling();
      }
    } catch (err) {
      if (isMountedRef.current) {
        setError(err.message || 'Failed to fetch workout status.');
        // If 404 or 403, stop polling
        if (err.status === 404 || err.status === 403) {
          stopPolling();
        }
      }
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
      }
    }
  }, [jobId, autoFetchDetails, stopPolling]);

  // Initial load and polling setup
  useEffect(() => {
    isMountedRef.current = true;
    setLoading(true);
    fetchJobData();

    // Start interval
    timerRef.current = setInterval(() => {
      fetchJobData();
    }, pollInterval);

    return () => {
      isMountedRef.current = false;
      stopPolling();
    };
  }, [jobId, pollInterval, fetchJobData, stopPolling]);

  const retry = async () => {
    if (!jobId) return;
    try {
      setIsRetrying(true);
      setError(null);
      await jobsApi.retryJob(jobId);
      stopPolling();
      await fetchJobData();
      timerRef.current = setInterval(() => {
        fetchJobData();
      }, pollInterval);
    } catch (err) {
      setError(err.message || 'Status refresh failed.');
    } finally {
      setIsRetrying(false);
    }
  };

  const switchVideoType = useCallback(async (type) => {
    if (!jobId) return;
    try {
      const url = await jobsApi.loadJobVideoUrl(jobId, type);
      if (isMountedRef.current && url) {
        setVideoUrl(url);
      }
    } catch (err) {
      console.error('Failed switching video feed:', err);
    }
  }, [jobId]);

  return {
    job,
    reps,
    report,
    videoUrl,
    loading,
    error,
    isRetrying,
    refetch: fetchJobData,
    retry,
    stopPolling,
    switchVideoType,
  };
}
