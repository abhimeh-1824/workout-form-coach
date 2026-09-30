/**
 * useJobs Hook
 *
 * Fetches and filters the user's workout job history, computing dashboard metrics.
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import { jobsApi } from '../services/jobsApi.js';
import { JOB_STATUSES } from '../utils/constants.js';

export function useJobs() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState('all'); // 'all' | 'processing' | 'completed' | 'failed'
  const [searchQuery, setSearchQuery] = useState('');

  const fetchJobs = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await jobsApi.getJobs();
      setJobs(data?.jobs || []);
    } catch (err) {
      setError(err.message || 'Failed to load workouts.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  // Filtered jobs list
  const filteredJobs = useMemo(() => {
    return jobs.filter((job) => {
      // Filter by status tab
      if (filter === 'processing') {
        if (job.status !== JOB_STATUSES.PROCESSING && job.status !== JOB_STATUSES.QUEUED) return false;
      } else if (filter === 'completed') {
        if (job.status !== JOB_STATUSES.COMPLETED) return false;
      } else if (filter === 'failed') {
        if (job.status !== JOB_STATUSES.FAILED) return false;
      }

      // Filter by search query
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase().trim();
        const exerciseName = (job.exercise_name || job.exercise || '').toLowerCase();
        const rig = (job.hardware_rig || '').toLowerCase();
        const id = (job.job_id || '').toLowerCase();
        return exerciseName.includes(query) || rig.includes(query) || id.includes(query);
      }

      return true;
    });
  }, [jobs, filter, searchQuery]);

  // Aggregate stats
  const stats = useMemo(() => {
    const total = jobs.length;
    const completed = jobs.filter((j) => j.status === JOB_STATUSES.COMPLETED);
    const completedCount = completed.length;
    const processingCount = jobs.filter((j) => j.status === JOB_STATUSES.PROCESSING || j.status === JOB_STATUSES.QUEUED).length;
    const failedCount = jobs.filter((j) => j.status === JOB_STATUSES.FAILED).length;

    let scoreSum = 0;
    let scoreCount = 0;
    completed.forEach((j) => {
      const s = j.report?.form_score;
      if (typeof s === 'number') {
        scoreSum += s;
        scoreCount += 1;
      }
    });

    const avgScore = scoreCount > 0 ? (scoreSum / scoreCount).toFixed(1) : (total > 0 ? '0' : '--');

    return {
      totalWorkouts: total,
      completedCount,
      processingCount,
      failedCount,
      avgFormScore: avgScore,
    };
  }, [jobs]);

  const deleteJob = useCallback(async (jobId) => {
    await jobsApi.deleteJob(jobId);
    setJobs((prev) => prev.filter((j) => j.job_id !== jobId));
  }, []);

  return {
    jobs,
    filteredJobs,
    loading,
    error,
    filter,
    setFilter,
    searchQuery,
    setSearchQuery,
    stats,
    refetch: fetchJobs,
    deleteJob,
  };
}
