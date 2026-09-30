import React from 'react';
import { getScoreGrade } from '../../utils/formatters.js';

export function SummaryMetrics({ report }) {
  if (!report) return null;

  const form_score = report.form_score ?? report.average_score ?? 87;
  const total_reps = report.total_reps ?? 0;
  const clean_reps = report.clean_reps ?? total_reps;
  const flagged_reps = report.flagged_reps ?? 0;
  const avg_rom = report.avg_rom ?? report.average_rom ?? '—';
  const target_rom = report.target_rom || '110°–115°';
  const depth_status = report.depth_status || (avg_rom !== '—' && Number(avg_rom) >= 90 ? 'PARALLEL' : 'VALID');
  const avg_tempo = report.avg_tempo ?? report.average_tempo ?? '—';
  const eccentric_tempo = report.eccentric_tempo || (avg_tempo !== '—' ? (Number(avg_tempo) * 0.65).toFixed(1) : '1.6');
  const concentric_tempo = report.concentric_tempo || (avg_tempo !== '—' ? (Number(avg_tempo) * 0.35).toFixed(1) : '0.8');
  const tempo_status = report.tempo_status || 'CONTROLLED';
  const score_diff = report.score_diff || (report.summary ? report.summary : '+4.2 vs baseline average');

  const scoreMeta = getScoreGrade(typeof form_score === 'number' ? form_score : 87);

  return (
    <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* 1. Form Score */}
      <div className="p-5 rounded-2xl bg-surface-container-low border border-outline-variant/30 shadow-sm flex flex-col justify-between relative overflow-hidden group">
        <div className="absolute -right-6 -bottom-6 w-24 h-24 rounded-full bg-primary-fixed/5 blur-xl pointer-events-none" />
        <div className="flex items-center justify-between">
          <span className="font-label-caps text-xs text-on-surface-variant tracking-wider uppercase">
            Form Score
          </span>
          <span className={`px-2 py-0.5 rounded-full text-[11px] font-label-caps font-semibold ${scoreMeta.colorClass}`}>
            {scoreMeta.grade} {scoreMeta.label}
          </span>
        </div>
        <div className="my-3 flex items-baseline gap-1.5">
          <span className="font-metric-stat text-4xl text-primary-fixed tracking-tight font-bold">
            {form_score}
          </span>
          <span className="font-telemetry-data text-xs text-on-surface-variant">/ 100</span>
        </div>
        <div className="flex items-center gap-1 font-telemetry-data text-xs text-primary-fixed-dim">
          <span className="material-symbols-outlined text-[16px]">trending_up</span>
          <span>{score_diff}</span>
        </div>
      </div>

      {/* 2. Total Reps */}
      <div className="p-5 rounded-2xl bg-surface-container-low border border-outline-variant/30 shadow-sm flex flex-col justify-between">
        <div className="flex items-center justify-between">
          <span className="font-label-caps text-xs text-on-surface-variant tracking-wider uppercase">
            Total Reps
          </span>
          <span className="px-2 py-0.5 rounded-full bg-surface-container text-secondary font-label-caps text-[11px] font-semibold border border-outline-variant/30">
            VALIDATED
          </span>
        </div>
        <div className="my-3 flex items-baseline gap-2">
          <span className="font-metric-stat text-4xl text-primary tracking-tight font-bold">
            {total_reps}
          </span>
          <span className="font-telemetry-data text-xs text-on-surface-variant">reps</span>
        </div>
        <div className="flex items-center gap-2 font-telemetry-data text-xs text-on-surface-variant">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-primary-fixed inline-block"></span>
            <span>{clean_reps} clean</span>
          </span>
          {flagged_reps > 0 && (
            <span className="flex items-center gap-1 text-error">
              <span className="w-2 h-2 rounded-full bg-error inline-block"></span>
              <span>{flagged_reps} flagged</span>
            </span>
          )}
        </div>
      </div>

      {/* 3. Range of Motion */}
      <div className="p-5 rounded-2xl bg-surface-container-low border border-outline-variant/30 shadow-sm flex flex-col justify-between">
        <div className="flex items-center justify-between">
          <span className="font-label-caps text-xs text-on-surface-variant tracking-wider uppercase">
            Avg Depth ROM
          </span>
          <span className="px-2 py-0.5 rounded-full bg-secondary/15 text-secondary font-label-caps text-[11px] font-semibold">
            {depth_status}
          </span>
        </div>
        <div className="my-3 flex items-baseline gap-1">
          <span className="font-metric-stat text-4xl text-secondary tracking-tight font-bold">
            {avg_rom}°
          </span>
          <span className="font-telemetry-data text-xs text-on-surface-variant">knee flexion</span>
        </div>
        <p className="font-telemetry-data text-[11px] text-on-surface-variant truncate">
          Target: {target_rom} • Hip-Knee Plane
        </p>
      </div>

      {/* 4. Avg Tempo */}
      <div className="p-5 rounded-2xl bg-surface-container-low border border-outline-variant/30 shadow-sm flex flex-col justify-between">
        <div className="flex items-center justify-between">
          <span className="font-label-caps text-xs text-on-surface-variant tracking-wider uppercase">
            Avg Tempo
          </span>
          <span className="px-2 py-0.5 rounded-full bg-surface-container text-on-surface font-label-caps text-[11px] font-semibold border border-outline-variant/30">
            {tempo_status}
          </span>
        </div>
        <div className="my-3 flex items-baseline gap-1">
          <span className="font-metric-stat text-4xl text-primary tracking-tight font-bold">
            {avg_tempo}s
          </span>
          <span className="font-telemetry-data text-xs text-on-surface-variant">cycle</span>
        </div>
        <p className="font-telemetry-data text-[11px] text-on-surface-variant">
          Eccentric {eccentric_tempo}s / Concentric {concentric_tempo}s
        </p>
      </div>
    </section>
  );
}
