import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth.js';
import { authApi } from '../../services/authApi.js';
import { OAuthButton } from '../../components/auth/OAuthButton.jsx';
import { Loader } from '../../components/common/Loader.jsx';

export function LoginPage() {
  const { isAuthenticated, checkAuth } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [errorMsg, setErrorMsg] = useState(null);
  const [isExchangingCode, setIsExchangingCode] = useState(false);

  // If already authenticated, redirect to dashboard
  useEffect(() => {
    if (isAuthenticated) {
      navigate('/dashboard', { replace: true });
    }
  }, [isAuthenticated, navigate]);

  // Handle OAuth PKCE callback (e.g. redirected back with ?code=...&state=...)
  useEffect(() => {
    const code = searchParams.get('code');
    const state = searchParams.get('state');
    const error = searchParams.get('error');

    if (error) {
      setErrorMsg(`Authentication error: ${error}`);
      return;
    }

    if (code && state) {
      setIsExchangingCode(true);
      authApi
        .exchangeCodeForToken({ code, state })
        .then(async () => {
          await checkAuth();
          navigate('/dashboard', { replace: true });
        })
        .catch((err) => {
          console.error('PKCE exchange error:', err);
          setErrorMsg(err.message || 'Failed to complete Google authentication.');
          setIsExchangingCode(false);
        });
    }
  }, [searchParams, checkAuth, navigate]);

  return (
    <main className="min-h-screen w-full bg-surface text-on-surface antialiased flex flex-col justify-center items-center px-4 py-8 relative selection:bg-primary-container selection:text-on-primary-container">
      {/* Background Biomechanical Skeletal Wireframe */}
      <div className="absolute inset-0 pointer-events-none -z-0 overflow-hidden opacity-30 flex items-center justify-center">
        <svg
          className="w-full max-w-[600px] h-auto max-h-[85vh]"
          viewBox="0 0 390 680"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <line x1="195" y1="90" x2="145" y2="155" stroke="#7bd0ff" strokeWidth="1.2" strokeDasharray="3 3" />
          <line x1="195" y1="90" x2="245" y2="155" stroke="#7bd0ff" strokeWidth="1.2" strokeDasharray="3 3" />
          <line x1="145" y1="155" x2="245" y2="155" stroke="#c8f322" strokeWidth="1" />
          <line x1="145" y1="155" x2="110" y2="240" stroke="#7bd0ff" strokeWidth="1.2" />
          <line x1="245" y1="155" x2="280" y2="240" stroke="#7bd0ff" strokeWidth="1.2" />
          <line x1="110" y1="240" x2="90" y2="330" stroke="#c8f322" strokeWidth="1.2" />
          <line x1="280" y1="240" x2="300" y2="330" stroke="#c8f322" strokeWidth="1.2" />
          <line x1="145" y1="155" x2="165" y2="310" stroke="#7bd0ff" strokeWidth="1" />
          <line x1="245" y1="155" x2="225" y2="310" stroke="#7bd0ff" strokeWidth="1" />
          <line x1="165" y1="310" x2="225" y2="310" stroke="#c8f322" strokeWidth="1" />
          <line x1="165" y1="310" x2="150" y2="440" stroke="#7bd0ff" strokeWidth="1.2" />
          <line x1="225" y1="310" x2="240" y2="440" stroke="#7bd0ff" strokeWidth="1.2" />
          <line x1="150" y1="440" x2="140" y2="570" stroke="#c8f322" strokeWidth="1.2" />
          <line x1="240" y1="440" x2="250" y2="570" stroke="#c8f322" strokeWidth="1.2" />
          <circle cx="195" cy="90" r="4" fill="#c8f322" />
          <circle cx="145" cy="155" r="3.5" fill="#7bd0ff" />
          <circle cx="245" cy="155" r="3.5" fill="#7bd0ff" />
          <circle cx="110" cy="240" r="3.5" fill="#c8f322" />
          <circle cx="280" cy="240" r="3.5" fill="#c8f322" />
          <circle cx="90" cy="330" r="3" fill="#7bd0ff" />
          <circle cx="300" cy="330" r="3" fill="#7bd0ff" />
          <circle cx="165" cy="310" r="3.5" fill="#c8f322" />
          <circle cx="225" cy="310" r="3.5" fill="#c8f322" />
          <circle cx="150" cy="440" r="4" fill="#7bd0ff" />
          <circle cx="240" cy="440" r="4" fill="#7bd0ff" />
          <circle cx="140" cy="570" r="3.5" fill="#c8f322" />
          <circle cx="250" cy="570" r="3.5" fill="#c8f322" />
        </svg>
      </div>

      <div className="w-full max-w-[420px] mx-auto flex flex-col relative z-10">
        {/* Brand Header */}
        <div className="flex flex-col items-center text-center mt-2 mb-6">
          <div className="relative flex items-center justify-center w-20 h-20 rounded-2xl bg-surface-container-high border border-outline-variant/40 shadow-xl mb-4 p-3">
            <div className="absolute inset-0 rounded-2xl bg-primary-container/10 -z-0"></div>
            <svg className="w-full h-full object-contain relative z-10" viewBox="0 0 40 40" fill="none">
              <circle cx="20" cy="9" r="4.5" fill="#c8f322" />
              <line x1="20" y1="13.5" x2="20" y2="24" stroke="#c8f322" strokeWidth="3" strokeLinecap="round" />
              <line x1="10" y1="18" x2="30" y2="18" stroke="#7bd0ff" strokeWidth="3" strokeLinecap="round" />
              <circle cx="10" cy="18" r="3" fill="#7bd0ff" />
              <circle cx="30" cy="18" r="3" fill="#7bd0ff" />
              <line x1="20" y1="24" x2="13" y2="34" stroke="#c8f322" strokeWidth="3" strokeLinecap="round" />
              <line x1="20" y1="24" x2="27" y2="34" stroke="#c8f322" strokeWidth="3" strokeLinecap="round" />
              <circle cx="13" cy="34" r="3" fill="#c8f322" />
              <circle cx="27" cy="34" r="3" fill="#c8f322" />
            </svg>
          </div>

          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-surface-container-high border border-outline-variant/30 mb-3">
            <span className="w-1.5 h-1.5 rounded-full bg-primary-container animate-pulse"></span>
            <span className="font-label-caps text-[11px] text-secondary uppercase tracking-widest">
              AI Workout Coach
            </span>
          </div>

          <h1 className="font-headline-lg text-3xl sm:text-4xl text-primary tracking-tight font-bold">
            Workout Form Coach
          </h1>
          <p className="font-body-md text-sm text-on-surface-variant font-medium mt-1">
            Analyze your form. Train smarter.
          </p>
        </div>

        {/* Main Card */}
        <div className="bg-surface-container rounded-2xl p-6 sm:p-7 shadow-2xl border border-outline-variant/40 flex flex-col gap-6">
          <p className="font-body-sm text-xs sm:text-sm text-on-surface-variant text-center leading-relaxed">
            Sign in to upload workout clips and track your reps, depth, and technique.
          </p>

          {/* Keypoints Chips */}
          <div className="flex flex-wrap items-center justify-center gap-2">
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-surface-container-highest text-primary border border-outline-variant/30">
              <span className="text-secondary text-xs">✦</span>
              <span className="font-telemetry-data text-xs font-semibold">Rep Counting</span>
            </div>
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-surface-container-highest text-primary border border-outline-variant/30">
              <span className="text-primary-container text-xs">●</span>
              <span className="font-telemetry-data text-xs font-semibold">Form Analysis</span>
            </div>
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-surface-container-highest text-primary border border-outline-variant/30">
              <span className="text-secondary text-xs">⚡</span>
              <span className="font-telemetry-data text-xs font-semibold">Instant Feedback</span>
            </div>
          </div>

          {/* Google Login Section (Exclusive auth method) */}
          <div className="flex flex-col gap-3 pt-2">
            {isExchangingCode ? (
              <div className="py-6 flex flex-col items-center justify-center gap-3">
                <Loader message="Completing authentication..." size="md" />
              </div>
            ) : (
              <OAuthButton onError={(err) => setErrorMsg(err)} />
            )}
          </div>

          {errorMsg && (
            <div className="p-3 rounded-lg bg-error-container/40 border border-error/40 text-error font-body-sm text-xs flex items-center gap-2">
              <span className="material-symbols-outlined text-[16px] shrink-0">error</span>
              <span>{errorMsg}</span>
            </div>
          )}

          {/* Security Notice */}
          <div className="flex items-start gap-2.5 p-3 rounded-xl bg-surface-container-low border border-outline-variant/30 text-on-surface-variant">
            <span className="material-symbols-outlined text-secondary text-[18px] mt-0.5 shrink-0">
              verified_user
            </span>
            <p className="font-body-sm text-xs leading-relaxed">
              Secured with PKCE (Proof Key for Code Exchange). Your workouts are processed privately.
            </p>
          </div>
        </div>

        {/* Footer info */}
        <div className="flex flex-col items-center gap-3 mt-6 text-center">
          <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-surface-container-low border border-outline-variant/30">
            <span className="w-2 h-2 rounded-full bg-primary-container"></span>
            <span className="font-telemetry-data text-xs text-on-surface font-semibold tracking-wide">
              Service Ready
            </span>
          </div>
          <div className="flex items-center gap-3 font-body-sm text-xs text-on-surface-variant">
            <a href="#terms" className="hover:text-primary transition-colors">Terms of Service</a>
            <span className="text-surface-container-highest">•</span>
            <a href="#privacy" className="hover:text-primary transition-colors">Privacy Policy</a>
          </div>
        </div>
      </div>
    </main>
  );
}
