import React from 'react';
import { RepRow } from './RepRow.jsx';

export function RepTimeline({ reps = [], selectedRep, onSelectRep }) {
  const cleanCount = reps.filter((r) => !r.is_flagged).length;
  const flaggedCount = reps.filter((r) => r.is_flagged).length;

  return (
    <section className="flex flex-col gap-4 p-5 sm:p-6 rounded-2xl bg-surface-container-low border border-outline-variant/30 shadow-sm">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="font-headline-md text-lg sm:text-xl text-primary font-bold">
            Rep-by-Rep Breakdown
          </h2>
          <p className="font-body-sm text-xs text-on-surface-variant mt-0.5">
            Select any rep to jump to that moment in the video and review depth, tempo, and technique.
          </p>
        </div>

        <div className="flex items-center gap-2 font-label-caps text-xs">
          <span className="px-2.5 py-1 rounded bg-primary-fixed/20 text-primary-fixed font-semibold">
            {cleanCount} CLEAN
          </span>
          {flaggedCount > 0 && (
            <span className="px-2.5 py-1 rounded bg-error-container text-on-error-container font-semibold">
              {flaggedCount} FLAGGED
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {reps.map((rep) => (
          <RepRow
            key={rep.rep_number}
            rep={rep}
            isSelected={selectedRep?.rep_number === rep.rep_number}
            onClick={() => onSelectRep(rep)}
          />
        ))}
      </div>
    </section>
  );
}
