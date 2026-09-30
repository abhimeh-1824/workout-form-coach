import React from 'react';

export function ErrorMessage({ title = 'Error', message, onRetry, className = '' }) {
  if (!message) return null;

  return (
    <div
      role="alert"
      className={`p-4 rounded-xl bg-error-container/30 border border-error/30 text-on-surface flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 ${className}`}
    >
      <div className="flex items-start gap-3">
        <span className="material-symbols-outlined text-error text-[22px] shrink-0 mt-0.5">
          error
        </span>
        <div className="flex flex-col">
          {title && <span className="font-headline-md text-sm text-error font-semibold">{title}</span>}
          <span className="font-body-sm text-xs text-on-surface-variant leading-relaxed">
            {message}
          </span>
        </div>
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="shrink-0 px-3 py-1.5 rounded-lg bg-surface-container hover:bg-surface-container-high text-primary font-body-sm text-xs font-semibold flex items-center gap-1.5 transition-colors border border-outline-variant/40"
        >
          <span className="material-symbols-outlined text-[16px]">refresh</span>
          <span>Retry</span>
        </button>
      )}
    </div>
  );
}
