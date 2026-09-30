import React from 'react';
import { formatTimeRange } from '../../utils/formatters.js';

export function RepRow({ rep, isSelected, onClick }) {
  if (!rep) return null;

  const {
    rep_number,
    start_time,
    end_time,
    rom,
    tempo,
    score,
    is_flagged,
    status_label,
    fault_label,
  } = rep;

  return (
    <div
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onClick();
        }
      }}
      className={`cursor-pointer p-4 rounded-xl border transition-all flex flex-col justify-between gap-2.5 text-left focus:outline-none ${
        isSelected
          ? is_flagged
            ? 'bg-surface-container-high border-error ring-2 ring-error shadow-md'
            : 'bg-surface-container-high border-primary-fixed ring-2 ring-primary-fixed shadow-md'
          : 'bg-surface-container border-outline-variant/30 hover:bg-surface-container-high hover:border-outline-variant'
      }`}
    >
      <div className="flex items-center justify-between">
        <span
          className={`font-headline-md text-sm sm:text-base font-bold ${
            is_flagged ? 'text-error' : 'text-primary'
          }`}
        >
          Rep {String(rep_number).padStart(2, '0')}
        </span>
        <span
          className={`font-label-caps text-[11px] font-bold ${
            is_flagged ? 'text-error' : 'text-primary-fixed'
          }`}
        >
          {is_flagged ? '⚠ FLAGGED' : '✓ CLEAN'}
        </span>
      </div>

      <div className="font-telemetry-data text-xs flex flex-col gap-0.5 text-on-surface-variant">
        <span>Time: {formatTimeRange(start_time, end_time)}</span>
        <span>
          ROM: <strong className={is_flagged && rom < 105 ? 'text-error' : 'text-on-surface'}>{rom}°</strong>
        </span>
        <span>
          Tempo: <strong className="text-on-surface">{tempo}s</strong>
        </span>
      </div>

      <div className="flex items-center justify-between pt-1 border-t border-outline-variant/20">
        <span
          className={`font-label-caps text-[10px] font-semibold truncate ${
            is_flagged ? 'text-error' : 'text-on-surface-variant'
          }`}
        >
          {is_flagged && fault_label ? fault_label : 'SCORE'}
        </span>
        <span
          className={`font-headline-md text-base sm:text-lg font-bold ${
            is_flagged ? 'text-error' : 'text-primary-fixed'
          }`}
        >
          {score}
        </span>
      </div>
    </div>
  );
}
