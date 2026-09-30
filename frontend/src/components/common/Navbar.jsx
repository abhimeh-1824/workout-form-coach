import React, { useState, useRef, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth.js';

export function Navbar() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef(null);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const isActive = (path) => location.pathname === path;

  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-surface/90 backdrop-blur-md border-b border-outline-variant/30 shadow-[0_4px_24px_-4px_rgba(0,0,0,0.5)]">
      <div className="h-20 max-w-7xl mx-auto px-4 sm:px-6 lg:px-10 flex items-center justify-between gap-4">
        {/* Brand & Nav */}
        <div className="flex items-center gap-6 lg:gap-10">
          <Link to="/dashboard" className="flex items-center gap-3 focus:outline-none group">
            <div className="w-9 h-9 rounded-lg bg-surface-container-high border border-outline-variant/40 flex items-center justify-center p-1.5 shadow-sm group-hover:border-primary-fixed/60 transition-colors">
              <svg className="w-full h-full" viewBox="0 0 40 40" fill="none">
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
            <span className="font-headline-md text-xl lg:text-2xl text-primary tracking-tight">
              Workout Form Coach
            </span>
          </Link>

          <nav className="hidden md:flex items-center gap-6 h-20">
            <Link
              to="/dashboard"
              className={`transition-colors py-2 uppercase tracking-wider text-xs font-semibold ${
                isActive('/dashboard')
                  ? 'text-primary-fixed border-b-2 border-primary-fixed'
                  : 'text-on-surface-variant hover:text-on-surface'
              }`}
            >
              Dashboard
            </Link>
            <Link
              to="/submit"
              className={`transition-colors py-2 uppercase tracking-wider text-xs font-semibold ${
                isActive('/submit')
                  ? 'text-primary-fixed border-b-2 border-primary-fixed'
                  : 'text-on-surface-variant hover:text-on-surface'
              }`}
            >
              + Analyze Workout
            </Link>
          </nav>
        </div>

        {/* User profile & Action */}
        <div className="flex items-center gap-2.5 sm:gap-3">
          <Link
            to="/submit"
            className="hidden sm:inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-primary-container text-on-primary-container font-headline-md text-xs font-bold hover:shadow-[0_0_16px_rgba(200,243,34,0.3)] transition-all"
          >
            <span className="material-symbols-outlined text-[16px]">add_circle</span>
            <span>New Video</span>
          </Link>

          {/* Profile Dropdown */}
          <div className="relative" ref={dropdownRef}>
            <button
              onClick={() => setDropdownOpen((prev) => !prev)}
              aria-haspopup="true"
              aria-expanded={dropdownOpen}
              className="flex items-center gap-1.5 p-1 bg-surface-container rounded-full border border-outline-variant/40 hover:border-primary-fixed/40 transition-all focus:outline-none"
              type="button"
            >
              <img
                src={
                  user?.avatarUrl ||
                  'https://lh3.googleusercontent.com/aida/AEtjO1XDwpvxjqOfZeUcBpFztZfBzXdTp1otFsQ1ZazZU9cpjyzlQN_xcf6HwR6UwbfLLG7czr0Rh4hiAUr2alF1NJSQwnqBRBUw1vB5ICYxdCN6TeZBAV0ISsozgJ2m-J8U3x23EUNVUyuB_Fcag4NrJPzF4DrML2RJKOqCGK8g7AJXdu01u-zo0o3Sfpi_TG_tS-eAXHBiLpChuqC8LUywmDaVdPVwaLWyBgE6CwOTZTr5ixYkqJq5-ZWWojp0'
                }
                alt={user?.name || 'Athlete profile'}
                className="w-8 h-8 rounded-full object-cover"
                referrerPolicy="no-referrer"
              />
              <span
                className={`material-symbols-outlined text-on-surface-variant text-[18px] pr-1 transition-transform duration-200 ${
                  dropdownOpen ? 'rotate-180' : ''
                }`}
              >
                expand_more
              </span>
            </button>

            {dropdownOpen && (
              <div className="absolute right-0 mt-2 w-60 rounded-xl bg-surface-container border border-outline-variant/30 shadow-[0_8px_32px_-4px_rgba(0,0,0,0.7)] py-2 z-50">
                <div className="px-4 py-2 border-b border-outline-variant/20 mb-1">
                  <p className="font-body-sm text-sm text-primary font-medium truncate">
                    {user?.name || 'Athlete Alex'}
                  </p>
                  <p className="font-telemetry-data text-[11px] text-on-surface-variant truncate">
                    {user?.email || 'alex@athletelab.dev'}
                  </p>
                  <span className="text-[11px] text-secondary font-medium mt-0.5 inline-block">
                    Active Account
                  </span>
                </div>

                <button
                  type="button"
                  onClick={() => {
                    setDropdownOpen(false);
                    navigate('/dashboard');
                  }}
                  className="w-full flex items-center gap-2.5 px-4 py-2 text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface transition-colors font-body-sm text-xs text-left"
                >
                  <span className="material-symbols-outlined text-[16px]">dashboard</span>
                  <span>Your Workouts</span>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setDropdownOpen(false);
                    navigate('/submit');
                  }}
                  className="w-full flex items-center gap-2.5 px-4 py-2 text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface transition-colors font-body-sm text-xs text-left"
                >
                  <span className="material-symbols-outlined text-[16px]">upload_file</span>
                  <span>Upload & Analyze</span>
                </button>

                <div className="my-1 border-t border-outline-variant/20"></div>

                <button
                  type="button"
                  onClick={() => {
                    setDropdownOpen(false);
                    logout();
                  }}
                  className="w-full flex items-center gap-2.5 px-4 py-2 text-error hover:bg-error-container/20 transition-colors font-body-sm text-xs text-left"
                >
                  <span className="material-symbols-outlined text-[16px]">logout</span>
                  <span>Sign Out</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
