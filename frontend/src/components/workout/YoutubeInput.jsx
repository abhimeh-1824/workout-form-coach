import React, { useState } from 'react';
import { validateYouTubeUrl } from '../../utils/validators.js';

export function YoutubeInput({ value, onChange, error, onError }) {
  const [touched, setTouched] = useState(false);

  const handleInputChange = (e) => {
    const val = e.target.value;
    onChange(val);

    if (val.trim()) {
      const res = validateYouTubeUrl(val);
      if (!res.valid) {
        if (onError) onError(res.error);
      } else {
        if (onError) onError(null);
      }
    } else {
      if (onError) onError(null);
    }
  };

  const handleBlur = () => {
    setTouched(true);
    if (value.trim()) {
      const res = validateYouTubeUrl(value);
      if (!res.valid && onError) {
        onError(res.error);
      }
    }
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <label className="font-label-caps text-xs text-on-surface-variant uppercase tracking-wider">
          YouTube Video Link
        </label>
        <span className="font-telemetry-data text-[11px] text-on-surface-variant">
          Max 60 seconds
        </span>
      </div>

      <div className="rounded-2xl bg-surface-container-low border border-outline-variant/40 p-5 flex flex-col gap-4 shadow-sm">
        <div className="relative flex items-center">
          <span className="material-symbols-outlined absolute left-3.5 text-on-surface-variant text-[20px]">
            link
          </span>
          <input
            type="url"
            value={value}
            onChange={handleInputChange}
            onBlur={handleBlur}
            placeholder="https://www.youtube.com/watch?v=..."
            className="w-full h-12 rounded-xl bg-surface-container text-primary placeholder:text-on-surface-variant/60 pl-11 pr-4 font-body-md text-sm border border-outline-variant/40 focus:outline-none focus:border-secondary focus:bg-surface-container-high transition-colors"
          />
        </div>

        <div className="p-3 rounded-lg bg-surface-container flex items-start gap-2.5 font-body-sm text-xs text-on-surface-variant">
          <span className="material-symbols-outlined text-secondary text-[18px] shrink-0 mt-0.5">
            info
          </span>
          <p className="leading-relaxed">
            Please make sure the link points to a public video where your full exercise movement is visible.
          </p>
        </div>

        {touched && error && (
          <div className="flex items-center gap-2 p-3 rounded-xl bg-error-container/30 border border-error/30 text-error font-body-sm text-xs">
            <span className="material-symbols-outlined text-[18px] shrink-0">error</span>
            <span>{error}</span>
          </div>
        )}
      </div>
    </div>
  );
}
