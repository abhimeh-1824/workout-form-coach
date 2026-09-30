import React from 'react';
import { EXERCISES } from '../../utils/constants.js';

export function ExerciseSelector({ selectedExercise, onSelect }) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <label className="font-label-caps text-xs text-on-surface-variant uppercase tracking-wider">
          1. Select Exercise Movement
        </label>
        <span className="font-telemetry-data text-[11px] text-secondary">
          3 Supported Movements
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {EXERCISES.map((ex) => {
          const isSelected = selectedExercise === ex.id;
          return (
            <button
              key={ex.id}
              type="button"
              onClick={() => onSelect(ex.id)}
              className={`p-4 rounded-xl border text-left transition-all flex flex-col justify-between gap-3 cursor-pointer ${
                isSelected
                  ? 'bg-surface-container-high border-primary-fixed shadow-[0_0_20px_rgba(200,243,34,0.15)] ring-1 ring-primary-fixed'
                  : 'bg-surface-container-low border-outline-variant/40 hover:bg-surface-container hover:border-outline-variant'
              }`}
            >
              <div className="flex items-start justify-between">
                <div
                  className={`w-10 h-10 rounded-lg flex items-center justify-center border ${
                    isSelected
                      ? 'bg-primary-container text-on-primary-container border-primary-container'
                      : 'bg-surface-container text-primary border-outline-variant/40'
                  }`}
                >
                  <span className="material-symbols-outlined text-[20px]">
                    {ex.icon}
                  </span>
                </div>
                {isSelected && (
                  <span className="material-symbols-outlined text-primary-fixed text-[18px]">
                    check_circle
                  </span>
                )}
              </div>

              <div>
                <h4 className="font-headline-md text-base text-primary font-semibold">
                  {ex.name}
                </h4>
                <p className="font-body-sm text-xs text-on-surface-variant mt-1 line-clamp-2">
                  {ex.description}
                </p>
              </div>

              <div className="pt-2 border-t border-outline-variant/30 flex flex-col gap-1 font-telemetry-data text-[11px]">
                <div className="flex items-center justify-between text-on-surface-variant">
                  <span>Standard Depth:</span>
                  <span className={isSelected ? 'text-secondary font-medium' : 'text-on-surface'}>
                    {ex.standardRom}
                  </span>
                </div>
                <div className="flex items-center justify-between text-on-surface-variant">
                  <span>Target Tempo:</span>
                  <span className={isSelected ? 'text-primary-fixed font-medium' : 'text-on-surface'}>
                    {ex.standardTempo}
                  </span>
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
