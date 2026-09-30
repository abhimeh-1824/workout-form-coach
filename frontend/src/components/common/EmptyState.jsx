import React from 'react';
import { Link } from 'react-router-dom';

export function EmptyState({
  title = 'No workout analyses yet',
  description = 'Upload a squat, push-up, or lunge video to get instant feedback on your reps, depth, and form.',
  actionLabel = 'Analyze New Workout',
  actionTo = '/submit',
  onAction,
}) {
  return (
    <div className="p-8 sm:p-12 rounded-2xl bg-surface-container-low border border-outline-variant/30 flex flex-col items-center justify-center text-center max-w-lg mx-auto shadow-md">
      <div className="w-16 h-16 rounded-2xl bg-surface-container flex items-center justify-center text-secondary mb-4 border border-outline-variant/40">
        <span className="material-symbols-outlined text-[32px]">sports_gymnastics</span>
      </div>
      <h3 className="font-headline-md text-xl text-primary font-bold tracking-tight">
        {title}
      </h3>
      <p className="font-body-md text-sm text-on-surface-variant max-w-md mt-2 mb-6 leading-relaxed">
        {description}
      </p>
      {actionTo ? (
        <Link
          to={actionTo}
          className="px-5 py-2.5 rounded-xl bg-primary-container text-on-primary-container font-headline-md text-sm font-semibold hover:shadow-[0_0_20px_rgba(200,243,34,0.3)] transition-all flex items-center gap-2"
        >
          <span className="material-symbols-outlined text-[18px]">add_circle</span>
          <span>{actionLabel}</span>
        </Link>
      ) : onAction ? (
        <button
          type="button"
          onClick={onAction}
          className="px-5 py-2.5 rounded-xl bg-primary-container text-on-primary-container font-headline-md text-sm font-semibold hover:shadow-[0_0_20px_rgba(200,243,34,0.3)] transition-all flex items-center gap-2"
        >
          <span className="material-symbols-outlined text-[18px]">add_circle</span>
          <span>{actionLabel}</span>
        </button>
      ) : null}
    </div>
  );
}
