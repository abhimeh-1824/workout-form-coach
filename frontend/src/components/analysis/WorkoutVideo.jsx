import React, { useState, useEffect } from 'react';
import { formatTime } from '../../utils/formatters.js';

export function WorkoutVideo({
  videoRef,
  videoUrl,
  selectedRep,
  reps = [],
  onSelectRep,
  videoFeedType = 'processed',
  onSwitchVideoFeed,
}) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [playbackRate, setPlaybackRate] = useState(1.0);
  const [activeOverlay, setActiveOverlay] = useState('none'); // 'none' (uses video-baked AI annotations) | 'skeleton'
  const [videoError, setVideoError] = useState(false);

  useEffect(() => {
    setVideoError(false);
  }, [videoUrl]);

  useEffect(() => {
    const video = videoRef?.current;
    if (!video) return;

    const handleTimeUpdate = () => {
      setCurrentTime(video.currentTime);
    };

    const handleLoadedMetadata = () => {
      if (Number.isFinite(video.duration)) {
        setDuration(video.duration);
      }
    };

    const handlePlay = () => setIsPlaying(true);
    const handlePause = () => setIsPlaying(false);
    const handleError = () => setVideoError(true);

    video.addEventListener('timeupdate', handleTimeUpdate);
    video.addEventListener('loadedmetadata', handleLoadedMetadata);
    video.addEventListener('play', handlePlay);
    video.addEventListener('pause', handlePause);
    video.addEventListener('error', handleError);

    if (!video.paused) {
      setIsPlaying(true);
    }
    if (Number.isFinite(video.duration) && video.duration > 0) {
      setDuration(video.duration);
    }

    return () => {
      video.removeEventListener('timeupdate', handleTimeUpdate);
      video.removeEventListener('loadedmetadata', handleLoadedMetadata);
      video.removeEventListener('play', handlePlay);
      video.removeEventListener('pause', handlePause);
      video.removeEventListener('error', handleError);
    };
  }, [videoRef, videoUrl]);

  const togglePlay = () => {
    const video = videoRef?.current;
    if (!video) return;
    if (video.paused) {
      video.play().then(() => setIsPlaying(true)).catch(() => {});
    } else {
      video.pause();
      setIsPlaying(false);
    }
  };

  const handleSkip = (seconds) => {
    const video = videoRef?.current;
    if (!video) return;
    const target = Math.max(0, Math.min(duration, video.currentTime + seconds));
    video.currentTime = target;
  };

  const handleRateChange = (rate) => {
    const video = videoRef?.current;
    if (video) {
      video.playbackRate = rate;
      setPlaybackRate(rate);
    }
  };

  const handleTimelineClick = (e) => {
    const video = videoRef?.current;
    const rect = e.currentTarget.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const percentage = Math.max(0, Math.min(1, clickX / rect.width));
    const target = percentage * (duration || 32);
    if (video) {
      video.currentTime = target;
    } else {
      setCurrentTime(target);
    }
  };

  const progressPercent = duration > 0 ? (currentTime / duration) * 100 : 0;

  return (
    <div className="flex flex-col bg-surface-container-lowest rounded-2xl overflow-hidden border border-outline-variant/40 shadow-xl">
      {/* Video Viewport with AI Biomechanical Overlay */}
      <div className="relative w-full aspect-[16/10] bg-black flex items-center justify-center overflow-hidden select-none">
        {/* Loading placeholder when video stream not yet ready */}
        {!videoUrl && !videoError && (
          <div className="absolute inset-0 flex flex-col items-center justify-center p-6 text-center z-10 bg-surface-container-lowest">
            <span className="material-symbols-outlined text-[48px] text-primary animate-spin mb-3">
              hourglass_top
            </span>
            <p className="font-headline-md text-sm text-primary font-semibold">
              Loading Workout Video Stream...
            </p>
            <p className="font-body-sm text-xs text-on-surface-variant mt-1">
              Synchronizing high-definition biomechanical video feed
            </p>
          </div>
        )}

        {/* Video Decoding / Load Error State */}
        {videoError && (
          <div className="absolute inset-0 flex flex-col items-center justify-center p-6 text-center z-20 bg-surface-container-lowest">
            <span className="material-symbols-outlined text-[48px] text-error mb-2">videocam_off</span>
            <p className="font-headline-md text-sm text-on-surface mb-1 font-semibold">
              Video Playback Error
            </p>
            <p className="font-body-sm text-xs text-on-surface-variant max-w-sm mb-4">
              Unable to decode video stream. Click below to reload.
            </p>
            <button
              type="button"
              onClick={() => {
                setVideoError(false);
                if (onSwitchVideoFeed) onSwitchVideoFeed(videoFeedType);
              }}
              className="px-4 py-2 rounded-xl bg-primary-fixed text-on-primary-fixed font-headline-md text-xs font-semibold hover:opacity-90 cursor-pointer"
            >
              Reload Video
            </button>
          </div>
        )}

        {/* HTML5 Native Video Element with Central Play Trigger */}
        {videoUrl && !videoError && (
          <>
            <video
              ref={videoRef}
              src={videoUrl}
              playsInline
              crossOrigin="use-credentials"
              className="absolute inset-0 w-full h-full object-contain z-10 cursor-pointer bg-black"
              onClick={togglePlay}
              onPlay={() => setIsPlaying(true)}
              onPause={() => setIsPlaying(false)}
              onEnded={() => setIsPlaying(false)}
              onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
              onLoadedMetadata={(e) => {
                if (Number.isFinite(e.currentTarget.duration)) {
                  setDuration(e.currentTarget.duration);
                }
              }}
              onError={() => setVideoError(true)}
            />
            {!isPlaying && (
              <button
                type="button"
                onClick={togglePlay}
                className="absolute inset-0 m-auto w-16 h-16 rounded-full bg-primary-fixed/90 hover:bg-primary-fixed text-on-primary-fixed flex items-center justify-center shadow-2xl backdrop-blur-sm z-20 transition-all hover:scale-110 cursor-pointer border border-outline-variant/30"
                aria-label="Play workout video"
              >
                <span className="material-symbols-outlined text-[36px]">play_arrow</span>
              </button>
            )}
          </>
        )}

        {/* Computer Vision Spatial Vector Calibration Layer */}
        {activeOverlay !== 'none' && (
          <svg
            className="absolute inset-0 w-full h-full pointer-events-none z-10"
            viewBox="0 0 800 500"
            fill="none"
          >
            {/* Spatial floor grid lines */}
            <line x1="150" y1="460" x2="650" y2="460" stroke="#444934" strokeDasharray="4 4" strokeWidth="1.5" />
            <line x1="200" y1="420" x2="600" y2="420" stroke="#444934" strokeDasharray="3 3" strokeWidth="1" opacity="0.6" />

            {/* Hip Depth Safe Plane Line (Cyan Dashed) */}
            <line x1="240" y1="330" x2="560" y2="330" stroke="#7bd0ff" strokeDasharray="6 4" strokeWidth="1.5" opacity="0.8" />
            <text x="565" y="334" fill="#7bd0ff" fontFamily="JetBrains Mono" fontSize="11" fontWeight="600">
              PARALLEL PLANE (110°)
            </text>

            {/* Skeleton Bones (Cyan & Lime precision segments) */}
            <line x1="390" y1="140" x2="385" y2="230" stroke="#c8f322" strokeWidth="3" strokeLinecap="round" />
            <line x1="335" y1="210" x2="445" y2="210" stroke="#7bd0ff" strokeWidth="3" strokeLinecap="round" />
            <line x1="385" y1="230" x2="375" y2="315" stroke="#c8f322" strokeWidth="3.5" strokeLinecap="round" />
            <line x1="330" y1="315" x2="420" y2="315" stroke="#7bd0ff" strokeWidth="3" strokeLinecap="round" />

            {/* Left Leg */}
            <line x1="330" y1="315" x2="310" y2="390" stroke="#7bd0ff" strokeWidth="3" strokeLinecap="round" />
            <line x1="310" y1="390" x2="315" y2="455" stroke="#7bd0ff" strokeWidth="3" strokeLinecap="round" />

            {/* Right Leg (Highlighted with deviation) */}
            <line
              x1="420"
              y1="315"
              x2="400"
              y2="385"
              stroke={selectedRep?.is_flagged ? '#ffb4ab' : '#c8f322'}
              strokeWidth="3.5"
              strokeLinecap="round"
            />
            <line
              x1="400"
              y1="385"
              x2="435"
              y2="455"
              stroke={selectedRep?.is_flagged ? '#ffb4ab' : '#7bd0ff'}
              strokeWidth="3.5"
              strokeLinecap="round"
            />

            {/* Joint Keypoints */}
            <circle cx="390" cy="140" r="14" fill="#1c2023" fillOpacity="0.8" stroke="#c8f322" strokeWidth="2" />
            <circle cx="335" cy="210" r="5" fill="#7bd0ff" />
            <circle cx="445" cy="210" r="5" fill="#7bd0ff" />
            <circle cx="330" cy="315" r="6" fill="#7bd0ff" />
            <circle cx="420" cy="315" r="7" fill={selectedRep?.is_flagged ? '#ffb4ab' : '#c8f322'} />
            <circle cx="310" cy="390" r="6" fill="#7bd0ff" />
            <circle
              cx="400"
              cy="385"
              r="8"
              fill={selectedRep?.is_flagged ? '#ffb4ab' : '#c8f322'}
              className="animate-pulse"
            />
            <circle cx="315" cy="455" r="5" fill="#7bd0ff" />
            <circle cx="435" cy="455" r="5" fill="#7bd0ff" />
          </svg>
        )}

        {/* Video Tracking Badge */}
        <div className="absolute top-3 left-3 z-20 px-2.5 py-1 rounded bg-surface-container-lowest/85 backdrop-blur font-telemetry-data text-[11px] text-on-surface-variant flex items-center gap-2 border border-outline-variant/30">
          <span className="flex items-center gap-1.5 text-primary-fixed">
            <span className="w-1.5 h-1.5 rounded-full bg-primary-fixed"></span>
            Pose Tracking Active
          </span>
        </div>

        {/* Active Rep Marker */}
        <div className="absolute top-3 right-3 z-20 px-2.5 py-1 rounded bg-surface-container-lowest/85 backdrop-blur font-label-caps text-xs text-primary flex items-center gap-1.5 border border-outline-variant/30">
          <span className={`w-2 h-2 rounded-full ${selectedRep?.is_flagged ? 'bg-error' : 'bg-primary-fixed'}`}></span>
          <span>REP {selectedRep?.rep_number || 2} OF {reps.length || 12}</span>
          <span className="text-on-surface-variant font-telemetry-data">
            {formatTime(currentTime)}
          </span>
        </div>

        {/* Dynamic Angle HUD Pinned Cards */}
        <div className="absolute top-[40%] left-[46%] -translate-y-1/2 p-2 rounded bg-surface-container-lowest/90 backdrop-blur font-telemetry-data text-xs text-secondary flex flex-col gap-0.5 border border-outline-variant/30 z-20 shadow-md">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[10px] text-on-surface-variant uppercase">Knee Flexion</span>
            <span className="font-bold text-secondary">{selectedRep?.rom || 108}°</span>
          </div>
          <div className="w-24 bg-surface-container h-1 rounded-full overflow-hidden">
            <div className="bg-secondary h-full" style={{ width: '82%' }}></div>
          </div>
        </div>

        <div className="absolute top-[26%] left-[26%] -translate-y-1/2 p-2 rounded bg-surface-container-lowest/90 backdrop-blur font-telemetry-data text-xs text-primary-fixed flex flex-col gap-0.5 border border-outline-variant/30 z-20 shadow-md">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[10px] text-on-surface-variant uppercase">Spine Angle</span>
            <span className="font-bold text-primary-fixed">34°</span>
          </div>
          <span className="text-[10px] text-primary-fixed-dim">Within ±5° Neutral</span>
        </div>

        {/* Targeted Anomaly Callout (if flagged rep selected) */}
        {selectedRep?.is_flagged && (
          <div className="absolute bottom-[22%] right-[18%] p-2 rounded-lg bg-error-container/90 text-on-error-container backdrop-blur shadow-lg flex items-start gap-2 max-w-[220px] border border-error/40 z-20">
            <span className="material-symbols-outlined text-[16px] text-error shrink-0 mt-0.5">
              warning
            </span>
            <div className="flex flex-col">
              <span className="font-label-caps text-[11px] font-bold text-error tracking-wide">
                {selectedRep?.fault_label || 'KNEE VALGUS (CAVE)'}
              </span>
              <span className="font-telemetry-data text-[10px] leading-tight text-on-error-container">
                -4.2° Inward Deviation at turnaround
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Integrated Scrubber & Timeline Bar */}
      <div className="p-4 bg-surface-container-low flex flex-col gap-3">
        {/* Timeline Scrubber with Rep Flag markers */}
        <div
          role="slider"
          aria-label="Workout video scrub timeline"
          aria-valuenow={Math.round(currentTime)}
          aria-valuemin={0}
          aria-valuemax={Math.round(duration)}
          tabIndex={0}
          onClick={handleTimelineClick}
          className="relative w-full h-7 flex items-center cursor-pointer group"
        >
          {/* Background Bar */}
          <div className="w-full h-2 rounded-full bg-surface-container-highest relative">
            {/* Played Progress */}
            <div
              className="absolute left-0 top-0 h-full rounded-full bg-secondary transition-all"
              style={{ width: `${progressPercent}%` }}
            />

            {/* Rep Markers (Dots) */}
            {reps.map((rep) => {
              const repPercent = duration > 0 ? (rep.start_time / duration) * 100 : (rep.rep_number / 12) * 100;
              const isSelected = selectedRep?.rep_number === rep.rep_number;
              return (
                <button
                  key={rep.rep_number}
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (onSelectRep) onSelectRep(rep);
                  }}
                  title={`Rep ${rep.rep_number}: ${
                    rep.is_flagged
                      ? (rep.fault_label || 'FLAGGED')
                      : (rep.status_label || 'CLEAN')
                  } (${rep.score ?? rep.form_score ?? 100})`}
                  className={`absolute top-1/2 -translate-y-1/2 w-3.5 h-3.5 rounded-full -ml-1.5 transition-transform hover:scale-125 focus:outline-none ${
                    rep.is_flagged
                      ? 'bg-error ring-2 ring-error-container'
                      : 'bg-primary-fixed'
                  } ${isSelected ? 'scale-125 ring-2 ring-primary' : ''}`}
                  style={{ left: `${Math.min(96, Math.max(4, repPercent))}%` }}
                />
              );
            })}
          </div>
        </div>

        {/* Playback Controls Strip */}
        <div className="flex flex-wrap items-center justify-between gap-3 font-telemetry-data text-xs">
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={() => handleSkip(-5)}
              aria-label="Replay 5 seconds"
              className="p-2 rounded-lg bg-surface-container hover:bg-surface-container-high text-primary flex items-center justify-center transition-colors"
            >
              <span className="material-symbols-outlined text-[18px]">replay_5</span>
            </button>

            <button
              type="button"
              onClick={togglePlay}
              aria-label={isPlaying ? 'Pause video' : 'Play video'}
              className="p-2 rounded-lg bg-primary-fixed text-on-primary-fixed font-bold flex items-center justify-center hover:opacity-90 transition-opacity"
            >
              <span className="material-symbols-outlined text-[20px]">
                {isPlaying ? 'pause' : 'play_arrow'}
              </span>
            </button>

            <button
              type="button"
              onClick={() => handleSkip(5)}
              aria-label="Forward 5 seconds"
              className="p-2 rounded-lg bg-surface-container hover:bg-surface-container-high text-primary flex items-center justify-center transition-colors"
            >
              <span className="material-symbols-outlined text-[18px]">forward_5</span>
            </button>

            <span className="ml-2 font-telemetry-data text-xs text-on-surface">
              {formatTime(currentTime)} / {formatTime(duration)}
            </span>
          </div>

          {/* Feed Switcher and Speed Toggles */}
          <div className="flex items-center gap-2">
            {onSwitchVideoFeed && (
              <div className="flex items-center gap-1 p-0.5 bg-surface-container rounded-lg font-label-caps text-[11px] border border-outline-variant/30">
                <button
                  type="button"
                  onClick={() => onSwitchVideoFeed('processed')}
                  className={`px-2.5 py-1 rounded transition-colors cursor-pointer ${
                    videoFeedType === 'processed'
                      ? 'bg-primary-fixed text-on-primary-fixed font-semibold'
                      : 'text-on-surface-variant hover:text-on-surface'
                  }`}
                >
                  AI Annotated
                </button>
                <button
                  type="button"
                  onClick={() => onSwitchVideoFeed('original')}
                  className={`px-2.5 py-1 rounded transition-colors cursor-pointer ${
                    videoFeedType === 'original'
                      ? 'bg-secondary/30 text-secondary font-semibold'
                      : 'text-on-surface-variant hover:text-on-surface'
                  }`}
                >
                  Original Video
                </button>
              </div>
            )}

            {/* Speed Toggle */}
            <button
              type="button"
              onClick={() => handleRateChange(playbackRate === 0.5 ? 1.0 : 0.5)}
              className={`px-2.5 py-1 rounded-lg font-label-caps text-xs transition-colors border border-outline-variant/30 cursor-pointer ${
                playbackRate === 0.5
                  ? 'bg-secondary/20 text-secondary font-semibold'
                  : 'bg-surface-container text-on-surface hover:bg-surface-container-high'
              }`}
            >
              {playbackRate}x
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
