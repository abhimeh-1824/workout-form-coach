import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { LoginPage } from '../pages/Login/LoginPage.jsx';
import { DashboardPage } from '../pages/Dashboard/DashboardPage.jsx';
import { SubmitWorkoutPage } from '../pages/SubmitWorkout/SubmitWorkoutPage.jsx';
import { JobDetailsPage } from '../pages/JobDetails/JobDetailsPage.jsx';
import { ProtectedRoute } from '../components/ProtectedRoute.jsx';

export function AppRoutes() {
  return (
    <Routes>
      {/* Public Authentication Route */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/auth/callback" element={<LoginPage />} />

      {/* Protected Routes */}
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/submit"
        element={
          <ProtectedRoute>
            <SubmitWorkoutPage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/jobs/:jobId"
        element={
          <ProtectedRoute>
            <JobDetailsPage />
          </ProtectedRoute>
        }
      />

      {/* Root redirect */}
      <Route path="/" element={<Navigate to="/dashboard" replace />} />

      {/* Wildcard 404 redirect */}
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
