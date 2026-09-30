import React, { useState, useRef, useEffect } from 'react';
import { validateVideoFile, checkVideoDuration } from '../../utils/validators.js';
import { formatFileSize, formatTime } from '../../utils/formatters.js';

export function VideoUploader({ file, onFileSelect, onFileRemove, error, onError }) {
  const [isDragging, setIsDragging] = useState(false);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [duration, setDuration] = useState(null);
  const [validatingMetadata, setValidatingMetadata] = useState(false);
  const fileInputRef = useRef(null);

  // Manage object URL memory safely
  useEffect(() => {
    if (!file) {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
        setPreviewUrl(null);
      }
      setDuration(null);
      return;
    }

    const url = URL.createObjectURL(file);
    setPreviewUrl(url);

    // Inspect duration
    setValidatingMetadata(true);
    checkVideoDuration(file).then((result) => {
      setValidatingMetadata(false);
      if (!result.valid) {
        if (onError) onError(result.error);
      } else {
        setDuration(result.duration || null);
      }
    });

    return () => {
      URL.revokeObjectURL(url);
    };
  }, [file, onError]);

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const droppedFiles = e.dataTransfer?.files;
    if (droppedFiles && droppedFiles.length > 0) {
      processSelectedFile(droppedFiles[0]);
    }
  };

  const handleInputChange = (e) => {
    const selectedFiles = e.target?.files;
    if (selectedFiles && selectedFiles.length > 0) {
      processSelectedFile(selectedFiles[0]);
    }
  };

  const processSelectedFile = (selectedFile) => {
    const validation = validateVideoFile(selectedFile);
    if (!validation.valid) {
      if (onError) onError(validation.error);
      return;
    }
    if (onError) onError(null);
    onFileSelect(selectedFile);
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <label className="font-label-caps text-xs text-on-surface-variant uppercase tracking-wider">
          2. Workout Video File
        </label>
        <span className="font-telemetry-data text-[11px] text-on-surface-variant">
          Max 100 MB • Max 60s duration
        </span>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept="video/mp4,video/quicktime,video/webm,video/x-m4v"
        onChange={handleInputChange}
        className="hidden"
        id="video-file-upload-input"
      />

      {!file ? (
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`border-2 border-dashed rounded-2xl p-8 sm:p-10 flex flex-col items-center justify-center text-center cursor-pointer transition-all duration-200 ${
            isDragging
              ? 'border-primary-fixed bg-primary-fixed/5'
              : 'border-outline-variant/50 hover:border-primary-fixed/50 bg-surface-container-low hover:bg-surface-container'
          }`}
        >
          <div className="w-16 h-16 rounded-full bg-surface-container flex items-center justify-center text-primary-fixed mb-4 border border-outline-variant/30">
            <span className="material-symbols-outlined text-[32px]">
              cloud_upload
            </span>
          </div>

          <h4 className="font-headline-md text-base sm:text-lg text-primary font-semibold">
            Drag & drop workout video here
          </h4>
          <p className="font-body-md text-xs sm:text-sm text-on-surface-variant max-w-sm mt-1 mb-4">
            Supports MP4, MOV, and WebM. Film from the side or 45° angle so your full movement is visible.
          </p>

          <button
            type="button"
            className="px-4 py-2 rounded-xl bg-surface-container-highest hover:bg-surface-bright text-primary font-body-sm text-xs font-semibold border border-outline-variant/40 transition-colors pointer-events-none"
          >
            Browse Files from Device
          </button>
        </div>
      ) : (
        <div className="rounded-2xl bg-surface-container-low border border-outline-variant/40 p-4 sm:p-5 flex flex-col gap-4 shadow-sm">
          {/* File details bar */}
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3 truncate">
              <div className="w-10 h-10 rounded-lg bg-surface-container flex items-center justify-center text-secondary shrink-0 border border-outline-variant/40">
                <span className="material-symbols-outlined text-[20px]">
                  videocam
                </span>
              </div>
              <div className="flex flex-col truncate">
                <span className="font-headline-md text-sm text-primary font-semibold truncate">
                  {file.name}
                </span>
                <span className="font-telemetry-data text-[11px] text-on-surface-variant">
                  {formatFileSize(file.size)}
                  {duration ? ` • ${formatTime(duration)}` : ''}
                  {validatingMetadata ? ' • Checking duration...' : ''}
                </span>
              </div>
            </div>

            <button
              type="button"
              onClick={onFileRemove}
              className="p-2 rounded-lg bg-surface-container hover:bg-error-container/30 text-on-surface-variant hover:text-error transition-colors shrink-0"
              title="Remove file"
            >
              <span className="material-symbols-outlined text-[18px]">close</span>
            </button>
          </div>

          {/* Embedded native preview player */}
          {previewUrl && (
            <div className="relative aspect-video rounded-xl bg-surface-container-lowest overflow-hidden border border-outline-variant/30 flex items-center justify-center">
              <video
                src={previewUrl}
                controls
                playsInline
                className="w-full h-full object-contain"
              />
            </div>
          )}
        </div>
      )}

      {error && (
        <div className="flex items-center gap-2 p-3 rounded-xl bg-error-container/30 border border-error/30 text-error font-body-sm text-xs">
          <span className="material-symbols-outlined text-[18px] shrink-0">error</span>
          <span>{error}</span>
        </div>
      )}
    </div>
  );
}
