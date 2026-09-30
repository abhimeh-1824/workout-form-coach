/**
 * Formatting and Safe Parsing Helpers
 */

/**
 * Format numeric seconds to MM:SS or MM:SS.S
 * @param {number|string} seconds
 * @returns {string}
 */
export function formatTime(seconds) {
  const num = Number(seconds);
  if (!Number.isFinite(num) || num < 0) return '00:00';

  const mins = Math.floor(num / 60);
  const secs = Math.floor(num % 60);
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

/**
 * Format seconds range for rep, e.g. "00:09 – 00:12"
 * @param {number} start
 * @param {number} end
 * @returns {string}
 */
export function formatTimeRange(start, end) {
  return `${formatTime(start)} – ${formatTime(end)}`;
}

/**
 * Safely parse a timestamp number for video seeking
 * Prevents NaN, infinite values, or crashes
 * @param {any} val
 * @param {number} maxDuration
 * @returns {number | null}
 */
export function safeTimestamp(val, maxDuration = 3600) {
  const num = Number(val);
  if (!Number.isFinite(num) || num < 0) return null;
  if (num > maxDuration) return maxDuration;
  return num;
}

/**
 * Get letter grade and color badge for a 0-100 form score
 * @param {number} score
 * @returns {{ grade: string, label: string, colorClass: string }}
 */
export function getScoreGrade(score) {
  const s = Number(score) || 0;
  if (s >= 93) return { grade: 'A+', label: 'EXEMPLARY', colorClass: 'text-primary-fixed bg-primary-container/20' };
  if (s >= 88) return { grade: 'A', label: 'OPTIMAL', colorClass: 'text-primary-fixed bg-primary-container/20' };
  if (s >= 82) return { grade: 'B+', label: 'GOOD FORM', colorClass: 'text-secondary bg-secondary/20' };
  if (s >= 75) return { grade: 'B', label: 'ACCEPTABLE', colorClass: 'text-secondary bg-secondary/15' };
  if (s >= 65) return { grade: 'C', label: 'NEEDS ADJUSTMENT', colorClass: 'text-amber-400 bg-amber-400/15' };
  return { grade: 'D', label: 'HIGH DEVIATION', colorClass: 'text-error bg-error-container/40' };
}

/**
 * Format bytes to readable size
 * @param {number} bytes
 * @returns {string}
 */
export function formatFileSize(bytes) {
  if (!bytes || bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
}

/**
 * Format ISO date string into human readable gym session label
 * @param {string} dateStr
 * @returns {string}
 */
export function formatJobDate(dateStr) {
  if (!dateStr) return 'Recently';
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    const now = new Date();
    const isToday = d.toDateString() === now.toDateString();
    const time = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    if (isToday) {
      return `Today at ${time}`;
    }
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    if (d.toDateString() === yesterday.toDateString()) {
      return `Yesterday at ${time}`;
    }
    return `${d.toLocaleDateString([], { month: 'short', day: 'numeric' })} at ${time}`;
  } catch {
    return dateStr;
  }
}
