/**
 * Input & Security Validators for Frontend UI/UX
 *
 * NOTE: Frontend validation is solely for responsive user experience.
 * Backend services remain the authoritative validation and security boundary.
 */

import { MAX_FILE_SIZE_BYTES, ALLOWED_MIME_TYPES, MAX_VIDEO_DURATION_SECONDS } from './constants.js';

/**
 * Validate a video file before upload
 * @param {File} file
 * @returns {{ valid: boolean, error: string | null }}
 */
export function validateVideoFile(file) {
  if (!file) {
    return { valid: false, error: 'Please select a video file.' };
  }

  if (file.size === 0) {
    return { valid: false, error: 'The selected file is empty (0 bytes).' };
  }

  if (file.size > MAX_FILE_SIZE_BYTES) {
    const sizeInMb = (file.size / (1024 * 1024)).toFixed(1);
    return {
      valid: false,
      error: `File size (${sizeInMb} MB) exceeds maximum allowed limit of 100 MB.`,
    };
  }

  // Check MIME type
  if (file.type && !ALLOWED_MIME_TYPES.includes(file.type.toLowerCase())) {
    return {
      valid: false,
      error: 'Unsupported file format. Please upload MP4, QuickTime (MOV), or WebM.',
    };
  }

  return { valid: true, error: null };
}

/**
 * Safely inspect video duration client-side where supported
 * @param {File} file
 * @returns {Promise<{ valid: boolean, duration?: number, error?: string }>}
 */
export function checkVideoDuration(file) {
  return new Promise((resolve) => {
    try {
      const url = URL.createObjectURL(file);
      const video = document.createElement('video');
      video.preload = 'metadata';

      video.onloadedmetadata = () => {
        URL.revokeObjectURL(url);
        const duration = video.duration;
        if (Number.isFinite(duration) && duration > MAX_VIDEO_DURATION_SECONDS) {
          resolve({
            valid: false,
            duration,
            error: `Video length (${Math.round(duration)}s) exceeds maximum allowed duration of ${MAX_VIDEO_DURATION_SECONDS}s.`,
          });
        } else {
          resolve({ valid: true, duration });
        }
      };

      video.onerror = () => {
        URL.revokeObjectURL(url);
        // If metadata fails to read in browser, let backend perform authoritative validation
        resolve({ valid: true, duration: 0 });
      };

      video.src = url;
    } catch {
      resolve({ valid: true, duration: 0 });
    }
  });
}

/**
 * Validate YouTube URL format
 * Disallows javascript:, data:, file:, arbitrary protocols, and enforces https YouTube domains.
 * @param {string} urlString
 * @returns {{ valid: boolean, error: string | null, videoId: string | null }}
 */
export function validateYouTubeUrl(urlString) {
  if (!urlString || typeof urlString !== 'string') {
    return { valid: false, error: 'YouTube URL cannot be empty.', videoId: null };
  }

  const trimmed = urlString.trim();

  // Reject dangerous protocols
  const lower = trimmed.toLowerCase();
  if (
    lower.startsWith('javascript:') ||
    lower.startsWith('data:') ||
    lower.startsWith('file:') ||
    lower.startsWith('vbscript:') ||
    lower.startsWith('blob:')
  ) {
    return { valid: false, error: 'Invalid URL protocol.', videoId: null };
  }

  if (!lower.startsWith('https://')) {
    return { valid: false, error: 'URL must use secure HTTPS protocol (https://).', videoId: null };
  }

  try {
    const parsed = new URL(trimmed);

    // Only allow expected YouTube hosts
    const allowedHosts = [
      'youtube.com',
      'www.youtube.com',
      'm.youtube.com',
      'youtu.be',
    ];

    if (!allowedHosts.includes(parsed.hostname.toLowerCase())) {
      return {
        valid: false,
        error: 'Please enter a valid YouTube URL (youtube.com or youtu.be).',
        videoId: null,
      };
    }

    let videoId = null;
    if (parsed.hostname.includes('youtu.be')) {
      videoId = parsed.pathname.slice(1).split('/')[0] || null;
    } else {
      videoId = parsed.searchParams.get('v');
    }

    if (!videoId && !parsed.pathname.includes('/shorts/')) {
      return {
        valid: false,
        error: 'Could not detect a valid YouTube video ID from the provided URL.',
        videoId: null,
      };
    }

    return { valid: true, error: null, videoId };
  } catch {
    return { valid: false, error: 'Malformed URL syntax.', videoId: null };
  }
}
