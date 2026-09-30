import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useJobs } from '../../hooks/useJobs.js';
import { useAuth } from '../../hooks/useAuth.js';
import { Navbar } from '../../components/common/Navbar.jsx';
import { JobCard } from '../../components/jobs/JobCard.jsx';
import { EmptyState } from '../../components/common/EmptyState.jsx';
import { Loader } from '../../components/common/Loader.jsx';
import { ErrorMessage } from '../../components/common/ErrorMessage.jsx';
import { jobsApi } from '../../services/jobsApi.js';

export function DashboardPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const {
    jobs,
    filteredJobs,
    loading,
    error,
    filter,
    setFilter,
    searchQuery,
    setSearchQuery,
    stats,
    refetch,
    deleteJob,
  } = useJobs();

  const handleRetryJob = async (jobId) => {
    try {
      await jobsApi.retryJob(jobId);
      refetch();
    } catch (err) {
      console.error('Retry error:', err);
    }
  };

  const handleDeleteJob = async (jobId) => {
    const confirmed = window.confirm(
      'Are you sure you want to permanently delete this workout session and all analysis data?'
    );
    if (!confirmed) return;

    try {
      await deleteJob(jobId);
    } catch (err) {
      alert(err.message || 'Failed to delete workout session.');
    }
  };

  return (
    <div className="bg-surface font-body-md text-on-surface antialiased min-h-screen flex flex-col">
      <Navbar />

      <main className="w-full pt-20 bg-surface flex-1">
        <div className="max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-10 py-8 lg:py-10 flex flex-col gap-10">
          {/* Top Action & Greeting Row */}
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-6">
            <div className="flex flex-col gap-1.5">
              <div className="flex items-center gap-2 font-label-caps text-xs text-secondary uppercase tracking-wider">
                <span className="w-2 h-2 rounded-full bg-secondary"></span>
                <span>
                  Welcome back, {user?.name?.split(' ')[0] || 'Athlete'}
                </span>
              </div>
              <h1 className="font-display-hero text-4xl sm:text-5xl lg:text-6xl text-primary tracking-tight leading-none">
                Your Workouts
              </h1>
              <p className="font-body-md text-sm sm:text-base text-on-surface-variant max-w-xl">
                Track your movement, check your rep depth, and improve your workout technique.
              </p>
            </div>

            <div className="flex items-center gap-3 shrink-0">
              <Link
                to="/submit"
                className="group relative flex items-center gap-2 px-5 py-3 bg-primary-container text-on-primary-container font-headline-md text-sm sm:text-base font-semibold rounded-xl hover:shadow-[0_0_24px_rgba(200,243,34,0.35)] transition-all duration-200"
              >
                <span className="material-symbols-outlined text-[20px] transition-transform duration-200 group-hover:scale-110">
                  upload_file
                </span>
                <span>+ Analyze New Workout</span>
              </Link>
            </div>
          </div>

          {/* Summary Metrics Section (3 Columns) */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {/* Metric Card 1 */}
            <div className="bg-surface-container-low border border-outline-variant/30 rounded-2xl p-6 flex flex-col justify-between shadow-sm relative overflow-hidden group">
              <div className="flex items-start justify-between">
                <div className="flex flex-col">
                  <span className="font-label-caps text-xs text-on-surface-variant uppercase tracking-wider">
                    Total Workouts
                  </span>
                  <span className="font-metric-stat text-4xl sm:text-5xl text-primary mt-2 font-bold tracking-tight">
                    {stats.totalWorkouts}
                  </span>
                </div>
                <div className="p-3 rounded-xl bg-surface-container text-secondary border border-outline-variant/30">
                  <span className="material-symbols-outlined text-[26px]">fitness_center</span>
                </div>
              </div>
              <div className="mt-6 pt-3 border-t border-outline-variant/20 flex items-center justify-between">
                <div className="flex items-center gap-1.5 text-secondary font-telemetry-data text-xs">
                  <span className="material-symbols-outlined text-[16px]">trending_up</span>
                  <span>+4 this week</span>
                </div>
                <span className="font-label-caps text-[11px] text-on-surface-variant">
                  Active
                </span>
              </div>
            </div>

            {/* Metric Card 2 */}
            <div className="bg-surface-container-low border border-outline-variant/30 rounded-2xl p-6 flex flex-col justify-between shadow-sm relative overflow-hidden group">
              <div className="flex items-start justify-between">
                <div className="flex flex-col">
                  <span className="font-label-caps text-xs text-on-surface-variant uppercase tracking-wider">
                    Completed Analyses
                  </span>
                  <span className="font-metric-stat text-4xl sm:text-5xl text-primary-fixed mt-2 font-bold tracking-tight">
                    {stats.completedCount}
                  </span>
                </div>
                <div className="p-3 rounded-xl bg-surface-container text-primary-fixed border border-outline-variant/30">
                  <span className="material-symbols-outlined text-[26px]">check_circle</span>
                </div>
              </div>
              <div className="mt-6 pt-3 border-t border-outline-variant/20 flex items-center justify-between">
                <div className="flex items-center gap-1.5 text-primary-fixed font-telemetry-data text-xs">
                  <span className="w-1.5 h-1.5 rounded-full bg-primary-fixed"></span>
                  <span>Feedback ready</span>
                </div>
                <span className="font-label-caps text-[11px] text-on-surface-variant">
                  Reviewed
                </span>
              </div>
            </div>

            {/* Metric Card 3 */}
            <div className="bg-surface-container-low border border-outline-variant/30 rounded-2xl p-6 flex flex-col justify-between shadow-sm relative overflow-hidden group">
              <div className="flex items-start justify-between">
                <div className="flex flex-col">
                  <span className="font-label-caps text-xs text-on-surface-variant uppercase tracking-wider">
                    Average Form Score
                  </span>
                  <div className="flex items-baseline gap-2 mt-2">
                    <span className="font-metric-stat text-4xl sm:text-5xl text-primary font-bold tracking-tight">
                      {stats.avgFormScore}
                    </span>
                    <span className="px-2 py-0.5 bg-primary-container/20 text-primary-fixed text-xs font-label-caps font-semibold rounded-md">
                      A- GRADE
                    </span>
                  </div>
                </div>
                {/* Circular Gauge SVG */}
                <div className="relative w-12 h-12 flex items-center justify-center">
                  <svg className="w-full h-full -rotate-90" viewBox="0 0 36 36">
                    <circle
                      className="stroke-surface-container-highest"
                      cx="18"
                      cy="18"
                      fill="none"
                      r="14"
                      strokeWidth="3"
                    />
                    <circle
                      className="stroke-primary-fixed"
                      cx="18"
                      cy="18"
                      fill="none"
                      r="14"
                      strokeDasharray="88, 100"
                      strokeLinecap="round"
                      strokeWidth="3"
                    />
                  </svg>
                  <span className="absolute material-symbols-outlined text-[16px] text-secondary">
                    verified
                  </span>
                </div>
              </div>
              <div className="mt-6 pt-3 border-t border-outline-variant/20 flex items-center justify-between">
                <div className="flex items-center gap-1.5 text-secondary font-telemetry-data text-xs">
                  <span className="material-symbols-outlined text-[16px]">arrow_upward</span>
                  <span>+3.2% vs last month</span>
                </div>
                <span className="font-label-caps text-[11px] text-on-surface-variant">
                  Consistent
                </span>
              </div>
            </div>
          </div>

          {/* Workout Jobs & Analysis Section */}
          <div className="flex flex-col gap-5">
            {/* Section Header with Filters and Search */}
            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-1">
              <div className="flex flex-wrap items-center gap-3">
                <h2 className="font-headline-md text-xl sm:text-2xl text-primary font-bold mr-2">
                  Workout History
                </h2>

                {/* Filter Badges */}
                <div className="flex items-center gap-1 p-1 bg-surface-container-low rounded-xl border border-outline-variant/30">
                  <button
                    type="button"
                    onClick={() => setFilter('all')}
                    className={`px-3.5 py-1.5 rounded-lg font-label-caps text-xs transition-colors cursor-pointer ${
                      filter === 'all'
                        ? 'text-primary-fixed bg-surface-container font-semibold shadow-sm'
                        : 'text-on-surface-variant hover:text-on-surface'
                    }`}
                  >
                    All ({jobs.length})
                  </button>
                  <button
                    type="button"
                    onClick={() => setFilter('processing')}
                    className={`px-3.5 py-1.5 rounded-lg font-label-caps text-xs transition-colors cursor-pointer ${
                      filter === 'processing'
                        ? 'text-secondary bg-surface-container font-semibold shadow-sm'
                        : 'text-on-surface-variant hover:text-on-surface'
                    }`}
                  >
                    Processing ({stats.processingCount})
                  </button>
                  <button
                    type="button"
                    onClick={() => setFilter('completed')}
                    className={`px-3.5 py-1.5 rounded-lg font-label-caps text-xs transition-colors cursor-pointer ${
                      filter === 'completed'
                        ? 'text-primary-fixed bg-surface-container font-semibold shadow-sm'
                        : 'text-on-surface-variant hover:text-on-surface'
                    }`}
                  >
                    Completed ({stats.completedCount})
                  </button>
                  <button
                    type="button"
                    onClick={() => setFilter('failed')}
                    className={`px-3.5 py-1.5 rounded-lg font-label-caps text-xs transition-colors cursor-pointer ${
                      filter === 'failed'
                        ? 'text-error bg-surface-container font-semibold shadow-sm'
                        : 'text-on-surface-variant hover:text-on-surface'
                    }`}
                  >
                    Failed ({stats.failedCount})
                  </button>
                </div>
              </div>

              {/* Search / Filter input */}
              <div className="relative w-full lg:w-72">
                <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-[18px] text-on-surface-variant">
                  search
                </span>
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Filter exercise or session..."
                  className="w-full bg-surface-container-low border border-outline-variant/30 text-primary placeholder-on-surface-variant/60 font-body-sm text-xs pl-9 pr-3 py-2 rounded-xl focus:outline-none focus:border-secondary focus:bg-surface-container transition-colors"
                />
              </div>
            </div>

            {error && (
              <ErrorMessage
                title="Unable to Load Workouts"
                message={error}
                onRetry={refetch}
              />
            )}

            {/* Pipeline List Items */}
            {loading ? (
              <div className="p-12 rounded-2xl bg-surface-container-low border border-outline-variant/30 flex flex-col items-center justify-center">
                <Loader message="Loading workouts..." />
              </div>
            ) : filteredJobs.length === 0 ? (
              <EmptyState
                title={searchQuery ? 'No matching workouts found' : 'No workout analyses yet'}
                description={
                  searchQuery
                    ? `No workouts matched "${searchQuery}". Try clearing your search.`
                    : 'Submit your first video or YouTube link to get rep counts and form analysis.'
                }
                actionLabel="Analyze New Workout"
                actionTo="/submit"
              />
            ) : (
              <div className="flex flex-col gap-3">
                {filteredJobs.map((job) => (
                  <JobCard
                    key={job.job_id}
                    job={job}
                    onRetry={handleRetryJob}
                    onDelete={handleDeleteJob}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Bottom Onboarding / Upload CTA Banner */}
          <div className="rounded-2xl bg-surface-container-low border border-outline-variant/30 p-6 sm:p-8 flex flex-col md:flex-row items-center justify-between gap-6 shadow-md">
            <div className="flex items-center gap-5">
              <div className="w-14 h-14 rounded-2xl bg-surface-container border border-outline-variant/40 flex items-center justify-center text-primary-fixed shrink-0">
                <span className="material-symbols-outlined text-[32px]">video_library</span>
              </div>
              <div className="flex flex-col">
                <h3 className="font-headline-md text-lg sm:text-xl text-primary font-bold">
                  Ready for your next set?
                </h3>
                <p className="font-body-md text-xs sm:text-sm text-on-surface-variant max-w-xl mt-1 leading-relaxed">
                  Record your exercise using your phone camera. Upload your clip to get rep counts, movement depth, and form coaching.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3 shrink-0 w-full md:w-auto">
              <Link
                to="/submit"
                className="w-full md:w-auto px-5 py-2.5 bg-primary-container text-on-primary-container font-headline-md text-xs sm:text-sm font-semibold rounded-xl hover:shadow-[0_0_20px_rgba(200,243,34,0.3)] transition-all flex items-center justify-center gap-1.5 text-center"
              >
                <span className="material-symbols-outlined text-[18px]">add_circle</span>
                <span>Upload Workout</span>
              </Link>
            </div>
          </div>
        </div>
      </main>

      {/* Global Footer */}
      <footer className="w-full bg-surface-container-lowest border-t border-outline-variant/20 py-6 mt-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-10 flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-on-surface-variant text-xs">
            <span className="w-2 h-2 rounded-full bg-primary-fixed"></span>
            <span>Workout Form Coach</span>
          </div>
          <p className="font-body-sm text-xs text-on-surface-variant text-center md:text-right">
            © 2025 Workout Form Coach. All rights reserved.
          </p>
        </div>
      </footer>
    </div>
  );
}
