import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Navbar } from '../../components/common/Navbar.jsx';
import { ExerciseSelector } from '../../components/workout/ExerciseSelector.jsx';
import { VideoUploader } from '../../components/workout/VideoUploader.jsx';
import { YoutubeInput } from '../../components/workout/YoutubeInput.jsx';
import { ErrorMessage } from '../../components/common/ErrorMessage.jsx';
import { jobsApi } from '../../services/jobsApi.js';
import { validateVideoFile, validateYouTubeUrl } from '../../utils/validators.js';

export function SubmitWorkoutPage() {
  const navigate = useNavigate();
  const [selectedExercise, setSelectedExercise] = useState('squat');
  const [sourceType, setSourceType] = useState('upload'); // 'upload' | 'youtube'
  const [videoFile, setVideoFile] = useState(null);
  const [youtubeUrl, setYoutubeUrl] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState(null);
  const [fieldError, setFieldError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFormError(null);

    // Validation
    if (!selectedExercise) {
      setFormError('Please select an exercise movement.');
      return;
    }

    if (sourceType === 'upload') {
      if (!videoFile) {
        setFormError('Please upload a workout video file to proceed.');
        return;
      }
      const fileValid = validateVideoFile(videoFile);
      if (!fileValid.valid) {
        setFormError(fileValid.error);
        return;
      }
    } else {
      if (!youtubeUrl.trim()) {
        setFormError('Please provide a valid YouTube video link.');
        return;
      }
      const urlValid = validateYouTubeUrl(youtubeUrl);
      if (!urlValid.valid) {
        setFormError(urlValid.error);
        return;
      }
    }

    try {
      setIsSubmitting(true);
      const submissionData = {
        exercise: selectedExercise,
        ...(sourceType === 'upload' ? { video: videoFile } : { youtube_url: youtubeUrl.trim() }),
      };

      // Call API
      const result = await jobsApi.createJob(submissionData);

      // Immediately navigate to /jobs/:jobId upon receiving queued status
      if (result?.job_id) {
        navigate(`/jobs/${result.job_id}`);
      } else {
        throw new Error('Could not start workout analysis. Please try again.');
      }
    } catch (err) {
      setFormError(err.message || 'Failed to submit workout for analysis.');
      setIsSubmitting(false);
    }
  };

  return (
    <div className="bg-surface font-body-md text-on-surface antialiased min-h-screen flex flex-col">
      <Navbar />

      <main className="w-full pt-20 bg-surface flex-1">
        <div className="max-w-4xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-8 lg:py-10 flex flex-col gap-8">
          {/* Header row */}
          <div className="flex flex-col gap-2">
            <Link
              to="/dashboard"
              className="inline-flex items-center gap-1.5 font-body-sm text-xs text-secondary hover:underline w-fit mb-1"
            >
              <span className="material-symbols-outlined text-[16px]">arrow_back</span>
              <span>Back to Dashboard</span>
            </Link>

            <div className="flex flex-wrap items-center gap-3">
              <h1 className="font-display-hero text-3xl sm:text-4xl text-primary tracking-tight font-bold">
                Submit Workout
              </h1>
            </div>

            <p className="font-body-md text-sm text-on-surface-variant max-w-2xl leading-relaxed">
              Upload your exercise video or paste a YouTube link to get your rep count and form feedback.
            </p>
          </div>

          {formError && (
            <ErrorMessage
              title="Submission Notice"
              message={formError}
              onRetry={() => setFormError(null)}
            />
          )}

          {/* Submission Form */}
          <form onSubmit={handleSubmit} className="flex flex-col gap-8">
            {/* 1. Exercise Selector */}
            <ExerciseSelector
              selectedExercise={selectedExercise}
              onSelect={(ex) => setSelectedExercise(ex)}
            />

            {/* Source Type Toggle */}
            <div className="flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <span className="font-label-caps text-xs text-on-surface-variant uppercase tracking-wider">
                  2. Choose Video Source
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3 p-1 rounded-xl bg-surface-container-low border border-outline-variant/30">
                <button
                  type="button"
                  onClick={() => {
                    setSourceType('upload');
                    setFormError(null);
                  }}
                  className={`py-3 rounded-lg font-headline-md text-xs sm:text-sm font-semibold flex items-center justify-center gap-2 transition-all cursor-pointer ${
                    sourceType === 'upload'
                      ? 'bg-surface-container text-primary border border-outline-variant/50 shadow-sm'
                      : 'text-on-surface-variant hover:text-on-surface'
                  }`}
                >
                  <span className="material-symbols-outlined text-[18px]">upload_file</span>
                  <span>Video Upload</span>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setSourceType('youtube');
                    setFormError(null);
                  }}
                  className={`py-3 rounded-lg font-headline-md text-xs sm:text-sm font-semibold flex items-center justify-center gap-2 transition-all cursor-pointer ${
                    sourceType === 'youtube'
                      ? 'bg-surface-container text-primary border border-outline-variant/50 shadow-sm'
                      : 'text-on-surface-variant hover:text-on-surface'
                  }`}
                >
                  <span className="material-symbols-outlined text-[18px]">smart_display</span>
                  <span>YouTube URL</span>
                </button>
              </div>
            </div>

            {/* Input Component based on active source type */}
            {sourceType === 'upload' ? (
              <VideoUploader
                file={videoFile}
                onFileSelect={(file) => setVideoFile(file)}
                onFileRemove={() => setVideoFile(null)}
                error={fieldError}
                onError={(err) => setFieldError(err)}
              />
            ) : (
              <YoutubeInput
                value={youtubeUrl}
                onChange={(val) => setYoutubeUrl(val)}
                error={fieldError}
                onError={(err) => setFieldError(err)}
              />
            )}

            {/* Privacy Notice */}
            <div className="p-4 rounded-xl bg-surface-container-low border border-outline-variant/30 flex items-start gap-3 text-on-surface-variant font-body-sm text-xs">
              <span className="material-symbols-outlined text-secondary text-[20px] shrink-0 mt-0.5">
                lock
              </span>
              <div className="flex flex-col gap-0.5">
                <span className="font-headline-md text-primary font-semibold text-xs">
                  Private & Secure
                </span>
                <p className="leading-relaxed">
                  Your workout videos are analyzed privately to evaluate your reps, depth, and form.
                </p>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-2 border-t border-outline-variant/20">
              <Link
                to="/dashboard"
                className="w-full sm:w-auto px-5 py-3 rounded-xl bg-surface-container hover:bg-surface-container-high text-on-surface font-body-sm text-xs sm:text-sm font-semibold text-center border border-outline-variant/40 transition-colors"
              >
                Cancel
              </Link>

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full sm:w-auto px-8 py-3.5 rounded-xl bg-primary-container text-on-primary-container font-headline-md text-sm sm:text-base font-bold flex items-center justify-center gap-2 hover:shadow-[0_0_24px_rgba(200,243,34,0.4)] transition-all cursor-pointer disabled:opacity-75 disabled:cursor-not-allowed"
              >
                {isSubmitting ? (
                  <>
                    <span className="material-symbols-outlined animate-spin text-[20px]">sync</span>
                    <span>Submitting workout...</span>
                  </>
                ) : (
                  <>
                    <span className="material-symbols-outlined text-[20px]">fitness_center</span>
                    <span>Analyze Workout</span>
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      </main>
    </div>
  );
}
