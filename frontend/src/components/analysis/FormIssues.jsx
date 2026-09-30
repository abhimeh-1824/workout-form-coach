import React from 'react';

export function FormIssues({ issues = [], kinematicScores }) {
  const scores = kinematicScores || {
    knee_path_tracking: 82,
    spine_neutrality: 94,
    hip_drive_symmetry: 91,
    bar_path_verticality: 88,
  };

  return (
    <div className="flex flex-col gap-4">
      {/* Form Issues */}
      <div className="p-5 rounded-2xl bg-surface-container-low border border-outline-variant/30 shadow-sm flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <h2 className="font-headline-md text-base sm:text-lg text-primary font-bold">
            Form Issues & Feedback
          </h2>
          <span className="px-2 py-0.5 rounded bg-error-container text-on-error-container font-label-caps text-[11px] font-semibold">
            {issues.length} Detected
          </span>
        </div>

        {issues.length === 0 ? (
          <div className="p-4 rounded-xl bg-surface-container border border-outline-variant/30 text-center font-body-sm text-xs text-on-surface-variant">
            <span className="material-symbols-outlined text-primary-fixed text-[24px] mb-1">
              verified
            </span>
            <p>No form issues detected across this session. Great technique!</p>
          </div>
        ) : (
          issues.map((issue) => {
            const isWarning = issue.severity === 'warning';
            return (
              <div
                key={issue.id || issue.title}
                className="p-4 rounded-xl bg-surface-container border border-outline-variant/30 flex flex-col gap-2 shadow-sm"
              >
                <div className="flex items-center justify-between">
                  <span
                    className={`inline-flex items-center gap-1 font-label-caps text-xs font-semibold ${
                      isWarning ? 'text-error' : 'text-secondary'
                    }`}
                  >
                    <span className="material-symbols-outlined text-[16px]">
                      {isWarning ? 'warning' : 'info'}
                    </span>
                    {issue.title}
                  </span>
                  {issue.reps_affected && (
                    <span className="font-telemetry-data text-[11px] text-on-surface-variant">
                      {issue.reps_affected}
                    </span>
                  )}
                </div>

                <p className="font-body-sm text-xs text-on-surface leading-relaxed">
                  {issue.description}
                </p>

                {issue.ai_cue && (
                  <div className="p-2.5 rounded-lg bg-surface-container-lowest border border-outline-variant/30 font-body-sm text-xs text-secondary flex items-start gap-2 mt-1">
                    <span className="material-symbols-outlined text-[16px] shrink-0 text-secondary mt-0.5">
                      lightbulb
                    </span>
                    <span className="leading-snug">
                      <strong className="font-semibold text-primary">Form Tip:</strong> {issue.ai_cue}
                    </span>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Movement Scores */}
      <div className="p-5 rounded-2xl bg-surface-container-low border border-outline-variant/30 shadow-sm flex flex-col gap-4">
        <h2 className="font-headline-md text-base sm:text-lg text-primary font-bold">
          Movement Scores
        </h2>

        <div className="flex flex-col gap-3 font-telemetry-data text-xs">
          {/* Knee Tracking */}
          <div className="flex flex-col gap-1">
            <div className="flex justify-between items-center">
              <span className="text-on-surface-variant">Knee Path Tracking</span>
              <span className="text-primary font-bold">{scores.knee_path_tracking || 82}%</span>
            </div>
            <div className="w-full bg-surface-container h-2 rounded-full overflow-hidden">
              <div
                className="bg-error h-full rounded-full transition-all duration-300"
                style={{ width: `${scores.knee_path_tracking || 82}%` }}
              />
            </div>
          </div>

          {/* Spine Neutrality */}
          <div className="flex flex-col gap-1">
            <div className="flex justify-between items-center">
              <span className="text-on-surface-variant">Spine Neutrality</span>
              <span className="text-primary-fixed font-bold">{scores.spine_neutrality || 94}%</span>
            </div>
            <div className="w-full bg-surface-container h-2 rounded-full overflow-hidden">
              <div
                className="bg-primary-fixed h-full rounded-full transition-all duration-300"
                style={{ width: `${scores.spine_neutrality || 94}%` }}
              />
            </div>
          </div>

          {/* Movement Symmetry */}
          <div className="flex flex-col gap-1">
            <div className="flex justify-between items-center">
              <span className="text-on-surface-variant">Movement Symmetry</span>
              <span className="text-secondary font-bold">{scores.hip_drive_symmetry || 91}%</span>
            </div>
            <div className="w-full bg-surface-container h-2 rounded-full overflow-hidden">
              <div
                className="bg-secondary h-full rounded-full transition-all duration-300"
                style={{ width: `${scores.hip_drive_symmetry || 91}%` }}
              />
            </div>
          </div>

          {/* Balance & Line */}
          <div className="flex flex-col gap-1">
            <div className="flex justify-between items-center">
              <span className="text-on-surface-variant">Balance & Alignment</span>
              <span className="text-primary font-bold">{scores.bar_path_verticality || 88}%</span>
            </div>
            <div className="w-full bg-surface-container h-2 rounded-full overflow-hidden">
              <div
                className="bg-primary-fixed h-full rounded-full transition-all duration-300"
                style={{ width: `${scores.bar_path_verticality || 88}%` }}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
