import React from 'react';
import { Link } from 'react-router-dom';
import { JobStatus } from './JobStatus.jsx';
import { JobProgress } from './JobProgress.jsx';
import { formatJobDate } from '../../utils/formatters.js';
import { JOB_STATUSES } from '../../utils/constants.js';

export function JobCard({ job, onRetry, onDelete }) {
  if (!job) return null;

  const {
    job_id,
    exercise,
    exercise_name,
    session_num,
    status,
    progress = 0,
    created_at,
    hardware_rig,
    report,
    error,
    queue_position,
    worker_note,
    current_step,
    active_inference,
  } = job;

  // Icon mapping
  const getExerciseIcon = () => {
    if (status === JOB_STATUSES.FAILED) return 'videocam_off';
    if (status === JOB_STATUSES.QUEUED) return 'hourglass_top';
    if (status === JOB_STATUSES.PROCESSING) return 'model_training';
    if (exercise === 'squat') return 'sports_gymnastics';
    if (exercise === 'lunge') return 'directions_walk';
    return 'fitness_center';
  };

  return (
    <div className="bg-surface-container-low hover:bg-surface-container transition-colors rounded-xl p-4 sm:p-5 border border-outline-variant/30 flex flex-col gap-4 shadow-sm">
      {/* Top Header Row */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        {/* Left: Icon & Meta */}
        <div className="flex items-start gap-3.5 min-w-[260px]">
          <div
            className={`w-12 h-12 rounded-xl flex items-center justify-center shrink-0 border border-outline-variant/40 ${
              status === JOB_STATUSES.FAILED
                ? 'bg-error-container/30 text-error'
                : status === JOB_STATUSES.PROCESSING
                ? 'bg-surface-container text-secondary'
                : status === JOB_STATUSES.QUEUED
                ? 'bg-surface-container text-on-surface-variant'
                : 'bg-surface-container text-primary'
            }`}
          >
            <span className="material-symbols-outlined text-[24px]">
              {getExerciseIcon()}
            </span>
          </div>

          <div className="flex flex-col">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-headline-md text-base sm:text-lg text-primary font-semibold">
                {exercise_name || exercise || 'Workout Session'}
              </span>
              <JobStatus status={status} queuePosition={queue_position} />
            </div>
            <span className="font-telemetry-data text-xs text-on-surface-variant mt-0.5">
              {formatJobDate(created_at)}
              {session_num ? ` • Session #${session_num}` : ''}
            </span>
          </div>
        </div>

        {/* Center: State-specific payload */}
        {status === JOB_STATUSES.COMPLETED && report && (
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 items-center py-2 lg:py-0 border-y lg:border-y-0 border-surface-container-highest/40 flex-1 px-0 lg:px-4">
            <div className="flex flex-col">
              <span className="font-label-caps text-[11px] text-on-surface-variant">
                REPS
              </span>
              <span className="font-headline-md text-sm sm:text-base text-primary font-semibold">
                {report.total_reps} Reps
              </span>
              <span className="font-telemetry-data text-[11px] text-secondary">
                {report.depth_status || 'Full Depth'} | {report.avg_tempo}s tempo
              </span>
            </div>

            <div className="flex flex-col">
              <span className="font-label-caps text-[11px] text-on-surface-variant">
                FORM SCORE
              </span>
              <div className="flex items-baseline gap-1">
                <span className="font-headline-md text-lg sm:text-xl text-primary-fixed font-bold">
                  {report.form_score}
                </span>
                <span className="text-on-surface-variant font-telemetry-data text-xs">
                  / 100
                </span>
              </div>
              <span className="font-telemetry-data text-[11px] text-on-surface-variant">
                {report.score_diff || 'Good technique'}
              </span>
            </div>

            <div className="hidden sm:flex flex-col">
              <span className="font-label-caps text-[11px] text-on-surface-variant">
                TECHNIQUE
              </span>
              <span className="font-telemetry-data text-xs text-on-surface">
                {report.flagged_reps === 0 ? 'All reps clean' : `${report.flagged_reps} flagged reps`}
              </span>
              <span className="font-telemetry-data text-[11px] text-primary-fixed">
                Full range verified
              </span>
            </div>
          </div>
        )}

        {status === JOB_STATUSES.QUEUED && (
          <div className="flex flex-col justify-center flex-1 px-0 lg:px-4">
            <span className="font-label-caps text-[11px] text-on-surface-variant">
              STATUS
            </span>
            <span className="font-telemetry-data text-xs text-on-surface">
              Your video is queued for analysis. Results will appear shortly.
            </span>
          </div>
        )}

        {status === JOB_STATUSES.FAILED && (
          <div className="flex flex-col max-w-md flex-1 px-0 lg:px-4">
            <span className="font-label-caps text-[11px] text-error font-semibold">
              COULD NOT ANALYZE VIDEO
            </span>
            <span className="font-telemetry-data text-xs text-on-surface leading-snug">
              {error?.message || 'Please upload a clear video where your full body is visible.'}
            </span>
          </div>
        )}

        {/* Right: Actions */}
        <div className="flex items-center justify-end gap-2 shrink-0">
          {status === JOB_STATUSES.COMPLETED && (
            <Link
              to={`/jobs/${job_id}`}
              className="flex items-center gap-1.5 px-3.5 py-2 bg-surface-container hover:bg-surface-container-high text-primary font-body-sm text-xs font-semibold rounded-lg transition-colors border border-outline-variant/40"
            >
              <span>View Analysis</span>
              <span className="material-symbols-outlined text-[16px]">arrow_forward</span>
            </Link>
          )}

          {status === JOB_STATUSES.PROCESSING && (
            <Link
              to={`/jobs/${job_id}`}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-surface-container hover:bg-surface-container-high text-secondary font-body-sm text-xs font-semibold rounded-lg transition-colors border border-outline-variant/40"
            >
              <span className="material-symbols-outlined text-[16px] animate-spin">
                progress_activity
              </span>
              <span>Analyzing...</span>
            </Link>
          )}

          {status === JOB_STATUSES.QUEUED && (
            <div className="flex items-center gap-2">
              <Link
                to={`/jobs/${job_id}`}
                className="px-3 py-1.5 bg-surface-container hover:bg-surface-container-high text-on-surface font-body-sm text-xs rounded-lg transition-colors border border-outline-variant/40"
              >
                Details
              </Link>
            </div>
          )}

          {status === JOB_STATUSES.FAILED && (
            <div className="flex items-center gap-2 flex-wrap">
              <Link
                to="/submit"
                className="flex items-center gap-1 px-3 py-1.5 bg-surface-container hover:bg-surface-container-high text-primary font-body-sm text-xs rounded-lg transition-colors border border-outline-variant/40"
              >
                <span className="material-symbols-outlined text-[15px]">upload</span>
                <span>Replace File</span>
              </Link>
              {onRetry && (
                <button
                  type="button"
                  onClick={() => onRetry(job_id)}
                  className="flex items-center gap-1 px-3 py-1.5 bg-error-container hover:bg-error-container/80 text-on-error-container font-body-sm text-xs font-semibold rounded-lg transition-colors"
                >
                  <span className="material-symbols-outlined text-[15px]">refresh</span>
                  <span>Retry</span>
                </button>
              )}
            </div>
          )}

          {onDelete && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onDelete(job_id);
              }}
              title="Delete workout"
              aria-label="Delete workout"
              className="p-2 rounded-lg bg-surface-container hover:bg-error-container/40 text-on-surface-variant hover:text-error transition-colors border border-outline-variant/40 cursor-pointer flex items-center justify-center shrink-0"
            >
              <span className="material-symbols-outlined text-[18px]">delete</span>
            </button>
          )}
        </div>
      </div>

      {/* Processing Progress Row */}
      {status === JOB_STATUSES.PROCESSING && (
        <div className="pt-2 border-t border-surface-container-highest/40">
          <JobProgress
            progress={progress}
            currentStep={current_step}
            activeInference={active_inference}
          />
        </div>
      )}
    </div>
  );
}
