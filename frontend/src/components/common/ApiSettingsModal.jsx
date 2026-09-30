import React, { useState, useEffect } from 'react';
import {
  getApiBaseUrl,
  setApiBaseUrl,
  isMockApiEnabled,
  setMockApiEnabled,
  testBackendConnection,
  DEFAULT_ENV_API_URL,
} from '../../services/apiConfig.js';

export function ApiSettingsModal({ isOpen, onClose }) {
  const [apiUrl, setApiUrl] = useState('');
  const [mockActive, setMockActive] = useState(true);
  const [pingState, setPingState] = useState({ testing: false, result: null });
  const [saveNotice, setSaveNotice] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setApiUrl(getApiBaseUrl());
      setMockActive(isMockApiEnabled());
      setPingState({ testing: false, result: null });
      setSaveNotice(false);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleTestConnection = async () => {
    setPingState({ testing: true, result: null });
    const res = await testBackendConnection(apiUrl);
    setPingState({ testing: false, result: res });
  };

  const handleSave = () => {
    setApiBaseUrl(apiUrl);
    setMockApiEnabled(mockActive);
    setSaveNotice(true);
    setTimeout(() => {
      window.location.reload();
    }, 600);
  };

  const handleResetDefault = () => {
    setApiUrl(DEFAULT_ENV_API_URL);
    setMockActive(true);
    setApiBaseUrl(DEFAULT_ENV_API_URL);
    setMockApiEnabled(true);
    setPingState({ testing: false, result: null });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-surface/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-surface-container rounded-2xl max-w-lg w-full p-6 sm:p-7 border border-outline-variant/40 shadow-2xl flex flex-col gap-5 text-on-surface">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-10 h-10 rounded-xl bg-surface-container-high border border-outline-variant/40 flex items-center justify-center text-secondary">
              <span className="material-symbols-outlined text-[22px]">settings_ethernet</span>
            </div>
            <div>
              <h3 className="font-headline-md text-lg sm:text-xl text-primary font-bold">
                API & Backend Connection
              </h3>
              <p className="font-body-sm text-xs text-on-surface-variant">
                Switch between Mock API and your live Python backend
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="w-8 h-8 rounded-lg bg-surface-container hover:bg-surface-container-highest flex items-center justify-center text-on-surface-variant hover:text-on-surface transition-colors"
          >
            <span className="material-symbols-outlined text-[18px]">close</span>
          </button>
        </div>

        {/* Mode Toggle Switch */}
        <div className="p-4 rounded-xl bg-surface-container-low border border-outline-variant/30 flex items-center justify-between">
          <div className="flex flex-col gap-0.5">
            <span className="font-headline-md text-sm text-primary font-bold">
              {mockActive ? 'Mock API Active (Demo)' : 'Live Python API Active'}
            </span>
            <span className="font-body-sm text-xs text-on-surface-variant">
              {mockActive
                ? 'Frontend runs with simulated squat, push-up, and lunge sessions'
                : 'Frontend sends real HTTP requests to your Python API'}
            </span>
          </div>

          <button
            type="button"
            onClick={() => setMockActive(!mockActive)}
            className={`w-14 h-8 rounded-full p-1 transition-colors relative flex items-center ${
              mockActive ? 'bg-secondary/20' : 'bg-primary-container'
            }`}
          >
            <div
              className={`w-6 h-6 rounded-full bg-surface shadow-md transform transition-transform ${
                mockActive ? 'translate-x-0' : 'translate-x-6'
              } flex items-center justify-center`}
            >
              <span className="material-symbols-outlined text-[14px] text-on-surface">
                {mockActive ? 'shuffle' : 'cloud_sync'}
              </span>
            </div>
          </button>
        </div>

        {/* Python API URL Input */}
        <div className="flex flex-col gap-2">
          <label className="font-label-caps text-xs text-on-surface-variant uppercase tracking-wider flex items-center justify-between">
            <span>Python Backend URL</span>
            <span className="text-secondary font-telemetry-data text-[10px]">
              FastAPI / Flask / Django
            </span>
          </label>
          <div className="flex gap-2">
            <input
              type="url"
              value={apiUrl}
              onChange={(e) => setApiUrl(e.target.value)}
              placeholder="http://localhost:8000"
              className="flex-1 h-11 rounded-xl bg-surface-container-low text-primary font-telemetry-data text-xs sm:text-sm px-3.5 border border-outline-variant/30 focus:outline-none focus:border-secondary"
            />
            <button
              type="button"
              onClick={handleTestConnection}
              disabled={pingState.testing || !apiUrl}
              className="px-3.5 h-11 rounded-xl bg-surface-container-high hover:bg-surface-container-highest border border-outline-variant/40 font-headline-md text-xs font-semibold text-primary flex items-center gap-1.5 transition-colors disabled:opacity-50"
            >
              <span className={`material-symbols-outlined text-[16px] ${pingState.testing ? 'animate-spin' : ''}`}>
                {pingState.testing ? 'sync' : 'network_ping'}
              </span>
              <span>Test Ping</span>
            </button>
          </div>
          <span className="font-body-sm text-[11px] text-on-surface-variant">
            Example: <code className="text-secondary font-telemetry-data">http://localhost:8000</code> or your deployed server URL.
          </span>
        </div>

        {/* Ping Test Status Banner */}
        {pingState.result && (
          <div
            className={`p-3 rounded-xl border flex items-center justify-between text-xs font-body-sm ${
              pingState.result.ok
                ? 'bg-primary-container/10 border-primary-fixed/40 text-primary-fixed'
                : 'bg-error-container/20 border-error/40 text-error'
            }`}
          >
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-[18px]">
                {pingState.result.ok ? 'check_circle' : 'error'}
              </span>
              <span>
                {pingState.result.ok
                  ? `Connected! Python backend responded successfully (${pingState.result.latencyMs}ms)`
                  : `Ping failed: ${pingState.result.error}`}
              </span>
            </div>
            {pingState.result.ok && (
              <span className="font-telemetry-data text-[11px] px-2 py-0.5 rounded bg-primary-fixed/20 text-primary font-bold">
                HTTP {pingState.result.status}
              </span>
            )}
          </div>
        )}

        {/* Quick Env Tip */}
        <div className="p-3 rounded-xl bg-surface-container-lowest border border-outline-variant/20 flex flex-col gap-1 text-[11px] font-body-sm text-on-surface-variant">
          <span className="font-semibold text-on-surface flex items-center gap-1">
            <span className="material-symbols-outlined text-[14px] text-secondary">info</span>
            Zero-Code Switch:
          </span>
          <p>
            When your Python API is ready, you can either toggle it here or set{' '}
            <code className="text-primary font-telemetry-data">VITE_API_BASE_URL=http://localhost:8000</code> and{' '}
            <code className="text-primary font-telemetry-data">VITE_USE_MOCK_API=false</code> in your <code className="text-secondary">.env</code> file.
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center justify-between gap-3 pt-2">
          <button
            type="button"
            onClick={handleResetDefault}
            className="font-headline-md text-xs text-on-surface-variant hover:text-on-surface transition-colors"
          >
            Reset to Default
          </button>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl bg-surface-container-high hover:bg-surface-bright text-on-surface font-headline-md text-xs font-semibold transition-colors"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleSave}
              className="px-5 py-2 rounded-xl bg-primary-container text-on-primary-container font-headline-md text-xs font-bold hover:shadow-[0_0_16px_rgba(200,243,34,0.3)] transition-all flex items-center gap-1.5"
            >
              {saveNotice ? (
                <>
                  <span className="material-symbols-outlined animate-spin text-[16px]">sync</span>
                  <span>Applying & Reloading...</span>
                </>
              ) : (
                <>
                  <span className="material-symbols-outlined text-[16px]">save</span>
                  <span>Save & Apply</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
