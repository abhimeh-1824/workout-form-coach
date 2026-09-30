import React, { useState, useRef, useEffect, useMemo } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { Navbar } from '../../components/common/Navbar.jsx';
import { SummaryMetrics } from '../../components/analysis/SummaryMetrics.jsx';
import { WorkoutVideo } from '../../components/analysis/WorkoutVideo.jsx';
import { RepTimeline } from '../../components/analysis/RepTimeline.jsx';
import { FormIssues } from '../../components/analysis/FormIssues.jsx';
import { Loader } from '../../components/common/Loader.jsx';
import { ErrorMessage } from '../../components/common/ErrorMessage.jsx';
import { useJobStatus } from '../../hooks/useJobStatus.js';
import { jobsApi } from '../../services/jobsApi.js';
import { safeTimestamp, formatJobDate } from '../../utils/formatters.js';
import { JOB_STATUSES, PIPELINE_STEPS } from '../../utils/constants.js';

export function JobDetailsPage() {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const videoRef = useRef(null);

  const {
    job,
    reps,
    report,
    videoUrl,
    loading,
    error,
    isRetrying,
    retry,
    switchVideoType,
  } = useJobStatus(jobId);

  const [selectedRep, setSelectedRep] = useState(null);
  const [videoFeedType, setVideoFeedType] = useState('processed'); // 'processed' | 'original'
  const [isDeleting, setIsDeleting] = useState(false);

  // Active status reflects the true backend job status
  const activeStatus = job?.status || JOB_STATUSES.COMPLETED;

  const handleDelete = async () => {
    if (!jobId) return;
    const confirmed = window.confirm(
      'Are you sure you want to permanently delete this workout session and all analysis data?'
    );
    if (!confirmed) return;

    try {
      setIsDeleting(true);
      await jobsApi.deleteJob(jobId);
      navigate('/dashboard');
    } catch (err) {
      alert(err.message || 'Failed to delete workout session.');
      setIsDeleting(false);
    }
  };

  // Set initial selected rep
  useEffect(() => {
    if (reps && reps.length > 0 && !selectedRep) {
      // Pick flagged rep 2 or first rep
      const defaultRep = reps.find((r) => r.is_flagged) || reps[0];
      setSelectedRep(defaultRep);
    }
  }, [reps, selectedRep]);

  // Biomechanics issues and report memoized at top level before any conditional returns
  const effectiveReport = report || job?.report;
  const effectiveIssues = useMemo(() => {
    if (reps && reps.length > 0) {
      return reps.flatMap((r) =>
        (r.issues || []).map((issue, idx) => ({
          ...issue,
          id: `${r.rep_number}_${issue.code || idx}`,
          title: issue.code ? issue.code.replace(/_/g, ' ') : 'FORM ISSUE',
          description: issue.message || 'Form deviation detected during this repetition.',
          severity: issue.severity || 'warning',
          reps_affected: `Rep ${r.rep_number}`,
          ai_cue: issue.ai_cue || (issue.severity === 'major' ? 'Maintain deliberate control and stability throughout the movement.' : 'Ensure proper joint alignment and consistent range of motion.'),
        }))
      );
    }
    if (job?.issues && job.issues.length > 0) {
      return job.issues;
    }
    return [];
  }, [reps, job?.issues]);

  // Handle clicking a rep -> seek video safely
  const handleSelectRep = (rep) => {
    if (!rep) return;
    setSelectedRep(rep);

    // Safely seek video
    try {
      const video = videoRef?.current;
      if (video && typeof rep.start_time !== 'undefined') {
        const parsedTime = safeTimestamp(rep.start_time, video.duration || 3600);
        if (parsedTime !== null && Number.isFinite(parsedTime)) {
          video.currentTime = parsedTime;
          // If video paused, attempt gentle play
          if (video.paused) {
            video.play().catch(() => {});
          }
        }
      }
    } catch (err) {
      console.warn('Safe video seek handled:', err);
    }
  };

  if (loading && !job) {
    return (
      <div className="bg-surface font-body-md text-on-surface antialiased min-h-screen flex flex-col">
        <Navbar />
        <main className="w-full pt-20 flex-1 flex items-center justify-center">
          <Loader message="Loading workout analysis..." />
        </main>
      </div>
    );
  }

  if (error && !job) {
    return (
      <div className="bg-surface font-body-md text-on-surface antialiased min-h-screen flex flex-col">
        <Navbar />
        <main className="w-full pt-20 flex-1 flex flex-col items-center justify-center p-6">
          <div className="max-w-md w-full">
            <ErrorMessage
              title="Workout Session Not Accessible"
              message={error}
            />
            <Link
              to="/dashboard"
              className="mt-4 inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-surface-container hover:bg-surface-container-high text-primary font-body-sm text-xs font-semibold"
            >
              <span className="material-symbols-outlined text-[16px]">arrow_back</span>
              <span>Return to Workouts Dashboard</span>
            </Link>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="bg-surface font-body-md text-on-surface antialiased min-h-screen flex flex-col">
      <Navbar />

      <main className="w-full pt-20 bg-surface flex-1">
        {/* MAIN VIEWPORT CONTAINER */}
        <div className="max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-10 py-8 lg:py-10 flex flex-col gap-8">
          {/* ==================== 1. COMPLETED VIEW ==================== */}
          {activeStatus === JOB_STATUSES.COMPLETED && (
            <div className="flex flex-col gap-8">
              {/* Top Action Bar & Session Metadata */}
              <section className="flex flex-col md:flex-row md:items-end justify-between gap-4">
                <div className="flex flex-col gap-2">
                  <Link
                    to="/dashboard"
                    className="inline-flex items-center gap-1 font-body-sm text-xs text-secondary hover:underline w-fit"
                  >
                    <span className="material-symbols-outlined text-[16px]">arrow_back</span>
                    <span>Back to Dashboard</span>
                  </Link>

                  <div className="flex flex-wrap items-center gap-3">
                    <h1 className="font-headline-lg text-2xl sm:text-3xl lg:text-4xl text-primary tracking-tight font-bold">
                      {job?.exercise_name || 'Squat Analysis'}
                    </h1>
                    <span className="inline-flex items-center gap-1.5 px-3 py-0.5 rounded-full bg-primary-fixed/15 text-primary-fixed font-label-caps text-xs font-semibold">
                      <span className="w-1.5 h-1.5 rounded-full bg-primary-fixed animate-pulse"></span>
                      COMPLETED
                    </span>
                  </div>

                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1 font-telemetry-data text-xs text-on-surface-variant">
                    <span>Session #{job?.session_num || 883} • {formatJobDate(job?.created_at)}</span>
                    <span className="text-outline-variant">/</span>
                    <span>{job?.exercise_name || 'Squat'}</span>
                  </div>
                </div>

                {/* Utility Export, Delete & Re-run Triggers */}
                <div className="flex items-center gap-2.5 flex-wrap">
                  <button
                    type="button"
                    onClick={() => alert('Analysis report link copied to clipboard.')}
                    className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-surface-container hover:bg-surface-container-high transition-colors font-body-sm text-xs text-on-surface shadow-sm border border-outline-variant/30 cursor-pointer"
                  >
                    <span className="material-symbols-outlined text-[18px]">share</span>
                    <span>Share Analysis</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => alert('Exporting workout summary CSV...')}
                    className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-surface-container hover:bg-surface-container-high transition-colors font-body-sm text-xs text-on-surface shadow-sm border border-outline-variant/30 cursor-pointer"
                  >
                    <span className="material-symbols-outlined text-[18px]">download</span>
                    <span>Export CSV</span>
                  </button>
                  <button
                    type="button"
                    onClick={handleDelete}
                    disabled={isDeleting}
                    className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-error-container/40 hover:bg-error-container/70 text-error transition-colors font-body-sm text-xs font-semibold shadow-sm border border-error/30 cursor-pointer disabled:opacity-50"
                  >
                    <span className="material-symbols-outlined text-[18px]">delete</span>
                    <span>{isDeleting ? 'Deleting...' : 'Delete Workout'}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => retry()}
                    disabled={isRetrying}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-primary-fixed text-on-primary-fixed font-headline-md text-xs font-semibold hover:opacity-90 transition-opacity shadow-sm cursor-pointer disabled:opacity-75"
                  >
                    <span className="material-symbols-outlined text-[18px]">restart_alt</span>
                    <span>{isRetrying ? 'Queuing Re-run...' : 'Re-run Analysis'}</span>
                  </button>
                </div>
              </section>

              {/* High-Impact 4-Metric Grid */}
              <SummaryMetrics report={effectiveReport} />

              {/* Main Split Telemetry Section (Hero Video Player + Biomechanical Issues) */}
              <section className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
                {/* Video Player & Pose Overlay (8 Cols) */}
                <div className="lg:col-span-8">
                  <WorkoutVideo
                    videoRef={videoRef}
                    videoUrl={videoUrl || job?.processed_video_url}
                    selectedRep={selectedRep}
                    reps={reps}
                    onSelectRep={handleSelectRep}
                    videoFeedType={videoFeedType}
                    onSwitchVideoFeed={(type) => {
                      setVideoFeedType(type);
                      switchVideoType(type);
                    }}
                  />
                </div>

                {/* Right Column: Form Issues & Joint Kinematics Breakdown (4 Cols) */}
                <div className="lg:col-span-4">
                  <FormIssues
                    issues={effectiveIssues}
                    kinematicScores={effectiveReport?.kinematic_scores}
                  />
                </div>
              </section>

              {/* Full-Width Interactive Rep Breakdown Table & Cards */}
              <RepTimeline
                reps={reps}
                selectedRep={selectedRep}
                onSelectRep={handleSelectRep}
              />
            </div>
          )}

          {/* ==================== 2. PROCESSING VIEW ==================== */}
          {activeStatus === JOB_STATUSES.PROCESSING && (
            <div className="flex flex-col gap-6 items-center justify-center py-8 min-h-[500px]">
              <div className="max-w-2xl w-full p-8 sm:p-10 rounded-2xl bg-surface-container-low border border-outline-variant/30 shadow-xl flex flex-col gap-6 text-center items-center">
                {/* Live Circular Radar Indicator */}
                <div className="relative w-28 h-28 flex items-center justify-center">
                  <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
                    <circle cx="50" cy="50" fill="none" r="42" stroke="#262a2e" strokeWidth="6"></circle>
                    <circle
                      cx="50"
                      cy="50"
                      fill="none"
                      r="42"
                      stroke="#c8f322"
                      strokeDasharray="264"
                      strokeDashoffset={264 - (264 * (job?.progress || 68)) / 100}
                      strokeLinecap="round"
                      strokeWidth="6"
                      className="transition-all duration-300"
                    ></circle>
                  </svg>
                  <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <span className="font-headline-md text-2xl text-primary-fixed font-bold">
                      {job?.progress || 68}%
                    </span>
                    <span className="font-label-caps text-[10px] text-on-surface-variant">PROGRESS</span>
                  </div>
                </div>

                <div className="flex flex-col gap-1">
                  <h2 className="font-headline-lg text-2xl sm:text-3xl text-primary tracking-tight font-bold">
                    Analyzing Your Workout...
                  </h2>
                  <p className="font-body-md text-sm text-on-surface-variant">
                    {job?.current_step || 'Analyzing movement and body posture'}
                  </p>
                  <span className="font-telemetry-data text-xs text-secondary mt-1">
                    Tracking reps, depth, and form technique
                  </span>
                </div>

                {/* 6-Step Automated Pipeline Progression */}
                <div className="w-full flex flex-col gap-2 text-left mt-2 font-telemetry-data text-xs">
                  {PIPELINE_STEPS.map((step) => {
                    const isStepDone = (job?.progress || 68) > (step.id * 16);
                    const isStepActive = !isStepDone && (job?.progress || 68) >= ((step.id - 1) * 16);

                    return (
                      <div
                        key={step.id}
                        className={`flex items-center justify-between p-3 rounded-lg border transition-colors ${
                          isStepActive
                            ? 'bg-surface-container-high border-secondary/50 text-secondary'
                            : isStepDone
                            ? 'bg-surface-container border-outline-variant/30 text-primary-fixed'
                            : 'bg-surface-container/50 border-outline-variant/20 text-on-surface-variant opacity-60'
                        }`}
                      >
                        <div className="flex items-center gap-2.5">
                          {isStepDone ? (
                            <span className="material-symbols-outlined text-[18px] text-primary-fixed">
                              check_circle
                            </span>
                          ) : isStepActive ? (
                            <span className="w-3.5 h-3.5 rounded-full bg-secondary animate-ping"></span>
                          ) : (
                            <span className="material-symbols-outlined text-[18px] text-on-surface-variant">
                              radio_button_unchecked
                            </span>
                          )}
                          <span className={isStepActive ? 'font-semibold' : ''}>
                            {step.id}. {step.label}
                          </span>
                        </div>
                        <span className="font-label-caps text-[11px]">
                          {isStepDone ? 'DONE' : isStepActive ? 'ACTIVE' : 'QUEUED'}
                        </span>
                      </div>
                    );
                  })}
                </div>

                <div className="flex items-center gap-3 pt-2">
                  <Link
                    to="/dashboard"
                    className="px-4 py-2 rounded-xl bg-surface-container hover:bg-surface-container-high text-on-surface font-body-sm text-xs transition-colors border border-outline-variant/30"
                  >
                    Back to Dashboard (Runs in background)
                  </Link>
                  <button
                    type="button"
                    onClick={handleDelete}
                    disabled={isDeleting}
                    className="px-4 py-2 rounded-xl bg-error-container/40 hover:bg-error-container/70 text-error font-body-sm text-xs font-semibold transition-colors border border-error/30 cursor-pointer disabled:opacity-50 inline-flex items-center gap-1.5"
                  >
                    <span className="material-symbols-outlined text-[16px]">delete</span>
                    <span>{isDeleting ? 'Deleting...' : 'Delete'}</span>
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* ==================== 3. QUEUED VIEW ==================== */}
          {activeStatus === JOB_STATUSES.QUEUED && (
            <div className="flex flex-col gap-6 items-center justify-center py-8 min-h-[500px]">
              <div className="max-w-xl w-full p-8 sm:p-10 rounded-2xl bg-surface-container-low border border-outline-variant/30 shadow-xl flex flex-col gap-6 text-center items-center">
                <div className="w-16 h-16 rounded-full bg-surface-container flex items-center justify-center text-secondary border border-outline-variant/30">
                  <span className="material-symbols-outlined text-[36px] animate-spin">
                    hourglass_top
                  </span>
                </div>

                <div className="flex flex-col gap-1.5">
                  <span className="font-label-caps text-xs text-secondary tracking-widest uppercase font-semibold">
                    Workout Queue
                  </span>
                  <h2 className="font-headline-lg text-2xl sm:text-3xl text-primary tracking-tight font-bold">
                    Your workout is queued for analysis.
                  </h2>
                  <p className="font-body-md text-sm text-on-surface-variant max-w-md">
                    Position #{job?.queue_position || 1} in queue. Estimated wait time:{' '}
                    <strong className="text-primary">{job?.estimated_wait || '30 seconds'}</strong>.
                  </p>
                </div>

                {/* Queue info box */}
                <div className="w-full p-4 rounded-xl bg-surface-container border border-outline-variant/30 font-telemetry-data text-xs text-left flex flex-col gap-2">
                  <div className="flex justify-between text-on-surface-variant">
                    <span>Exercise:</span>
                    <span className="text-primary uppercase">{job?.exercise || 'Squat'}</span>
                  </div>
                  <div className="flex justify-between text-on-surface-variant">
                    <span>Status:</span>
                    <span className="text-secondary font-medium">In Queue</span>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <Link
                    to="/dashboard"
                    className="px-4 py-2 rounded-xl bg-surface-container hover:bg-surface-container-high text-on-surface font-body-sm text-xs transition-colors border border-outline-variant/30"
                  >
                    Back to Dashboard
                  </Link>
                  <button
                    type="button"
                    onClick={handleDelete}
                    disabled={isDeleting}
                    className="px-4 py-2 rounded-xl bg-error-container/40 hover:bg-error-container/70 text-error font-body-sm text-xs font-semibold transition-colors border border-error/30 cursor-pointer disabled:opacity-50 inline-flex items-center gap-1.5"
                  >
                    <span className="material-symbols-outlined text-[16px]">delete</span>
                    <span>{isDeleting ? 'Deleting...' : 'Delete'}</span>
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* ==================== 4. FAILED VIEW ==================== */}
          {activeStatus === JOB_STATUSES.FAILED && (
            <div className="flex flex-col gap-6 items-center justify-center py-8 min-h-[500px]">
              <div className="max-w-xl w-full p-8 sm:p-10 rounded-2xl bg-surface-container-low border border-error/40 shadow-xl flex flex-col gap-6 text-center items-center">
                <div className="w-16 h-16 rounded-full bg-error-container/40 text-error flex items-center justify-center border border-error/30">
                  <span className="material-symbols-outlined text-[36px]">error</span>
                </div>

                <div className="flex flex-col gap-1.5">
                  <span className="font-label-caps text-xs text-error tracking-widest uppercase font-semibold">
                    Analysis Notice
                  </span>
                  <h2 className="font-headline-lg text-2xl sm:text-3xl text-primary tracking-tight font-bold">
                    Could Not Analyze Video
                  </h2>
                  <p className="font-body-md text-sm text-on-surface-variant max-w-md">
                    {job?.error_message ||
                      job?.error?.message ||
                      'The camera view was obstructed or lighting was too dim to track your movement clearly.'}
                  </p>
                </div>

                {/* Diagnostics box */}
                <div className="w-full p-4 rounded-xl bg-surface-container border border-error/30 text-left flex flex-col gap-1.5 font-telemetry-data text-xs">
                  <span className="text-error font-semibold">Tips for Best Results:</span>
                  <p className="text-on-surface-variant text-xs leading-relaxed">
                    Ensure your full body is visible from head to toe, filmed with good lighting and no foreground objects blocking your view.
                  </p>
                </div>

                {/* Action triggers */}
                <div className="flex flex-wrap items-center justify-center gap-3 w-full">
                  <button
                    type="button"
                    onClick={() => retry()}
                    disabled={isRetrying}
                    className="px-5 py-2.5 rounded-xl bg-primary-fixed text-on-primary-fixed font-headline-md text-xs font-semibold hover:opacity-90 transition-opacity flex items-center gap-1.5 cursor-pointer disabled:opacity-75"
                  >
                    <span className="material-symbols-outlined text-[16px]">refresh</span>
                    <span>{isRetrying ? 'Retrying...' : 'Try Again'}</span>
                  </button>
                  <button
                    type="button"
                    onClick={handleDelete}
                    disabled={isDeleting}
                    className="px-5 py-2.5 rounded-xl bg-error-container/40 hover:bg-error-container/70 text-error font-headline-md text-xs font-semibold transition-colors border border-error/30 cursor-pointer disabled:opacity-50 flex items-center gap-1.5"
                  >
                    <span className="material-symbols-outlined text-[16px]">delete</span>
                    <span>{isDeleting ? 'Deleting...' : 'Delete Workout'}</span>
                  </button>
                  <Link
                    to="/submit"
                    className="px-5 py-2.5 rounded-xl bg-surface-container hover:bg-surface-container-high text-on-surface font-headline-md text-xs transition-colors border border-outline-variant/30 flex items-center gap-1.5"
                  >
                    <span className="material-symbols-outlined text-[16px]">upload</span>
                    <span>Replace Video File</span>
                  </Link>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
