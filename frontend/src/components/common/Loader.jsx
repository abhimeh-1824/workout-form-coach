import React from 'react';

export function Loader({ message = 'Loading...', size = 'md' }) {
  const sizeClasses = {
    sm: 'w-6 h-6 border-2',
    md: 'w-10 h-10 border-3',
    lg: 'w-16 h-16 border-4',
  };

  return (
    <div className="flex flex-col items-center justify-center gap-3 p-6 text-center">
      <div className="relative flex items-center justify-center">
        <div
          className={`${sizeClasses[size] || sizeClasses.md} rounded-full border-surface-container-highest border-t-primary-fixed animate-spin`}
        />
        <span className="w-2 h-2 rounded-full bg-primary-fixed animate-ping absolute" />
      </div>
      {message && (
        <p className="font-telemetry-data text-xs text-on-surface-variant font-medium tracking-wide">
          {message}
        </p>
      )}
    </div>
  );
}
