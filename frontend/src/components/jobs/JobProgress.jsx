import React from 'react';

export function JobProgress({ progress = 0, currentStep, activeInference }) {
  const boundedProgress = Math.max(0, Math.min(100, Math.round(progress)));

  return (
    <div className="flex flex-col gap-1.5 w-full">
      <div className="flex items-center justify-between font-telemetry-data text-xs">
        <span className="text-on-surface truncate pr-2">
          {currentStep || 'Analyzing workout movement...'}
        </span>
        <span className="text-secondary font-semibold shrink-0">
          {boundedProgress}%
        </span>
      </div>
      <div className="w-full h-2 rounded-full bg-surface-container overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-secondary-container via-secondary to-primary-fixed rounded-full transition-all duration-300 ease-out"
          style={{ width: `${boundedProgress}%` }}
        />
      </div>
      {activeInference && (
        <span className="font-telemetry-data text-[11px] text-on-surface-variant">
          {activeInference}
        </span>
      )}
    </div>
  );
}
