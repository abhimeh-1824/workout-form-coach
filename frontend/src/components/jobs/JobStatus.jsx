import React from 'react';
import { JOB_STATUSES } from '../../utils/constants.js';

export function JobStatus({ status, queuePosition = null, className = '' }) {
  switch (status) {
    case JOB_STATUSES.COMPLETED:
      return (
        <span
          className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-primary-container/15 text-primary-fixed text-[11px] font-label-caps font-semibold ${className}`}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-primary-fixed"></span>
          COMPLETED
        </span>
      );

    case JOB_STATUSES.PROCESSING:
      return (
        <span
          className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-secondary/15 text-secondary text-[11px] font-label-caps font-semibold ${className}`}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-secondary animate-ping"></span>
          ANALYZING FORM
        </span>
      );

    case JOB_STATUSES.QUEUED:
      return (
        <span
          className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-surface-container-high text-on-surface-variant text-[11px] font-label-caps font-semibold ${className}`}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-on-surface-variant"></span>
          QUEUED {queuePosition ? `#${queuePosition}` : ''}
        </span>
      );

    case JOB_STATUSES.FAILED:
      return (
        <span
          className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-error-container/40 text-error text-[11px] font-label-caps font-semibold ${className}`}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-error"></span>
          FAILED
        </span>
      );

    default:
      return (
        <span
          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-surface-container text-on-surface-variant text-[11px] font-label-caps font-semibold ${className}`}
        >
          {status}
        </span>
      );
  }
}
