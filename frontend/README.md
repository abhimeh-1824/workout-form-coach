# Workout Form Coach (Frontend)

> **Architectural Note:** The frontend is strictly API-driven and the backend implementation is intentionally decoupled. The backend may be developed using Python/FastAPI, Go, or any other server technology without requiring frontend refactoring.

Workout Form Coach is a web application for athletes and coaches providing AI-powered biomechanical vision analysis for squats, push-ups, and lunges. Athletes submit workout video feeds or YouTube links, monitor asynchronous GPU processing queues, and review 33-point 3D kinematic pose landmarks, rep cadence, range of motion (ROM) depth, and biomechanical fault flagging.

---

## Features

1. **OAuth & Session Authentication:**
   - Decoupled OAuth integration with Google endpoint (`GET /auth/google`)
   - Clean session checking via `GET /auth/me` with `credentials: 'include'` for secure HttpOnly cookies
   - Protected route guards redirecting unauthenticated traffic to `/login`

2. **Workouts Dashboard:**
   - Real-time aggregation of Total Workouts, Completed Analyses, and Average Biomechanical Form Score (with grade pills and stability tracking)
   - Analysis Pipeline feed with status badges (`completed`, `processing`, `queued`, `failed`)
   - Client-side search and category filtering
   - Quick action triggers: View Analysis, Live Telemetry, Retry, and Replace File

3. **Workout Submission Pipeline:**
   - Multi-input ingest: Direct video file upload or server-ingested YouTube link
   - Exercise movement selector for Squat, Push-up, and Lunge with target ROM and tempo guidance
   - Client-side UX validation: Max 100 MB, max 60s duration, supported MIME types (MP4, MOV, WebM), and HTTPS YouTube URL syntax
   - Instant response handling: Navigates immediately to `/jobs/:jobId` upon queued allocation without blocking UI

4. **Biomechanical Analysis & Kinematics Studio (`/jobs/:jobId`):**
   - 4-stat metric dashboard: Form Score (0–100), Validated Rep Counts (clean vs flagged), Avg Depth ROM, and Avg Tempo cycle
   - Processed video player with computer vision vector skeleton overlay and dynamic angle HUDs
   - Rep-by-rep biomechanics timeline with clean/flagged status
   - Interactive rep scrubbing: Clicking any rep card highlights the rep, displays issues, and safely seeks the video player to `rep.start_time`
   - Biomechanical Fault Diagnostics: Specific joint deviations (e.g. Knee Valgus, Shallow Depth) paired with contextual AI coaching cues
   - Kinematic breakdown bars: Knee Path Tracking, Spine Neutrality, Hip Drive Symmetry, and Bar Path Verticality
   - Comprehensive status views: Completed analysis, 6-step progress state, queued GPU allocation, and body occlusion failure diagnostics

---

## Tech Stack

- **Framework:** React 19 + Vite
- **Language:** JavaScript (ESNext / JSX — strictly decoupled from TypeScript)
- **Routing:** React Router v7 (`react-router-dom`)
- **Styling:** Tailwind CSS v4 with bespoke Stitch design tokens (Space Grotesk, Plus Jakarta Sans, JetBrains Mono)
- **State Management:** React Context (`AuthContext`) + Custom Hooks (`useJobs`, `useJobStatus`)
- **HTTP / Service Layer:** Centralized `apiClient` wrapping Fetch API with timeout (`AbortController`), credential inclusion, and unified error mapping

---

## Architecture & Folder Structure

```
├── .env.example                # Example environment variables
├── index.html                  # HTML entry point with design system fonts
├── package.json
├── README.md
├── src/
│   ├── app/
│   │   ├── App.jsx             # Top-level Router & Provider wrapper
│   │   └── routes.jsx          # Route declarations & ProtectedRoute guards
│   ├── components/
│   │   ├── analysis/
│   │   │   ├── FormIssues.jsx      # Fault cards & Kinematic breakdown
│   │   │   ├── RepRow.jsx          # Individual rep card
│   │   │   ├── RepTimeline.jsx     # Rep timeline container
│   │   │   ├── SummaryMetrics.jsx  # 4-card metric strip
│   │   │   └── WorkoutVideo.jsx    # Native video player + CV vector overlay
│   │   ├── auth/
│   │   │   └── OAuthButton.jsx     # Google OAuth trigger button
│   │   ├── common/
│   │   │   ├── Button.jsx
│   │   │   ├── Card.jsx
│   │   │   ├── EmptyState.jsx
│   │   │   ├── ErrorMessage.jsx
│   │   │   ├── Loader.jsx
│   │   │   └── Navbar.jsx          # Header with branding, navigation & profile
│   │   ├── jobs/
│   │   │   ├── JobCard.jsx         # Pipeline workout row card
│   │   │   ├── JobProgress.jsx     # Gradient progress bar
│   │   │   └── JobStatus.jsx       # Status badges (completed/processing/queued/failed)
│   │   ├── workout/
│   │   │   ├── ExerciseSelector.jsx # Squat / Push-up / Lunge cards
│   │   │   ├── VideoUploader.jsx    # Drag-and-drop file upload with preview
│   │   │   └── YoutubeInput.jsx     # Secure YouTube link input
│   │   └── ProtectedRoute.jsx       # Unauthenticated redirect guard
│   ├── context/
│   │   └── AuthContext.jsx         # User session, login, logout context
│   ├── hooks/
│   │   ├── useAuth.js              # Hook for authentication state
│   │   ├── useJobs.js              # Hook for dashboard jobs & statistics
│   │   └── useJobStatus.js         # Configurable polling hook for async jobs
│   ├── pages/
│   │   ├── Dashboard/
│   │   │   └── DashboardPage.jsx   # /dashboard view
│   │   ├── JobDetails/
│   │   │   └── JobDetailsPage.jsx  # /jobs/:jobId view
│   │   ├── Login/
│   │   │   └── LoginPage.jsx       # /login view
│   │   └── SubmitWorkout/
│   │       └── SubmitWorkoutPage.jsx # /submit view
│   ├── services/
│   │   ├── apiClient.js            # HTTP client (credentials, timeouts, errors)
│   │   ├── apiEndpoints.js         # Single contract for all API paths
│   │   ├── authApi.js              # Authentication service abstraction
│   │   ├── jobsApi.js              # Workout jobs service abstraction
│   │   └── mockData.js             # Realistic mock data & progression simulation
│   └── utils/
│       ├── constants.js            # Supported exercises, statuses, limits
│       ├── formatters.js           # Time, ROM, grades, and safe timestamp parsing
│       └── validators.js           # Client-side video and URL validators
```

---

## API Contract

The frontend communicates exclusively through `src/services/apiEndpoints.js`:

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Vision cluster health check |
| `GET` | `/auth/me` | Fetch authenticated athlete profile |
| `GET` | `/auth/google` | Initiate Google OAuth redirect |
| `POST` | `/auth/logout` | Terminate session cookies |
| `GET` | `/jobs` | List user workout jobs |
| `POST` | `/jobs` | Submit new workout (`multipart/form-data` or JSON) |
| `GET` | `/jobs/:jobId` | Poll job status, progress, and metadata |
| `GET` | `/jobs/:jobId/reps` | Fetch rep-by-rep kinematics telemetry |
| `GET` | `/jobs/:jobId/report` | Fetch completed summary report |
| `POST` | `/jobs/:jobId/retry` | Re-queue a failed analysis job |

### Expected POST `/jobs` Response
```json
{
  "job_id": "job_883_squat",
  "status": "queued"
}
```

### Expected Completed Job Response (`GET /jobs/:jobId`)
```json
{
  "job_id": "job_883_squat",
  "exercise": "squat",
  "status": "completed",
  "progress": 100,
  "processed_video_url": "https://.../video.mp4",
  "report": {
    "total_reps": 12,
    "form_score": 87,
    "avg_rom": 108,
    "avg_tempo": 2.4
  }
}
```

---

## Environment Variables & Configuration

Create a `.env` file in the root directory:

```bash
# Base URL for the backend API (FastAPI, Express, etc.)
VITE_API_BASE_URL=http://localhost:8000

# Toggle Mock API mode (true for frontend development without backend)
VITE_USE_MOCK_API=true
```

- When `VITE_USE_MOCK_API=true`, all API calls return realistic biomechanical data and simulate asynchronous polling transitions.
- When `VITE_USE_MOCK_API=false`, the app connects to the configured `VITE_API_BASE_URL`.

---

## Security Considerations

1. **No Client-side Secrets or Tokens:** The frontend does not store access or refresh tokens in `localStorage` or `sessionStorage`. Authentication relies on HttpOnly, SameSite, Secure cookies.
2. **Untrusted Data Policy:** All API-returned values, filenames, and descriptions are treated as untrusted and rendered safely without `dangerouslySetInnerHTML`.
3. **Safe Video Seeking:** All rep timestamps are verified with `Number.isFinite` and bounded against video duration to prevent browser crashes.
4. **Memory Management:** Object URLs created for video previews (`URL.createObjectURL`) are systematically revoked upon component unmount or file replacement.
5. **SSRF Guard:** YouTube video URLs are validated with regex for HTTPS and allowed domains on the client, with authoritative SSRF and internal IP protection reserved for the backend.
6. **Production Headers:** Production deployments should enforce `Content-Security-Policy`, `X-Content-Type-Options: nosniff`, and `Strict-Transport-Security` on the reverse proxy.

---

## Development & Production Build

### Install Dependencies
```bash
npm install
```

### Start Development Server
```bash
npm run dev
```
Dev server runs on `http://localhost:3000`.

### Production Build
```bash
npm run build
```
Generates optimized, production-ready static assets in `/dist`.

### One-Command Docker Setup
```bash
docker compose up --build
```
Launches containerized production NGINX on `http://localhost:3000` with the health probe active on `/health`.

---

## Work Session Log (FalcRise Tech Assignment)

| Session | Time Window (IST) | Work Performed |
|---|---|---|
| **Session 1** | 09:00 – 11:30 | Technical specification review, design system tokens extraction from Stitch UX, project initialization with Vite + React 19, and Tailwind CSS v4 setup. |
| **Session 2** | 11:45 – 13:45 | Architecture design: Centralized `apiClient.js` with credentials and timeout, `apiEndpoints.js` single contract, and `AuthContext` with Google OAuth abstraction. |
| **Session 3** | 14:30 – 17:00 | Component implementation: Authentication (`/login`), Workouts Dashboard (`/dashboard`) with metrics cards and pipeline filters, and Workout Submission (`/submit`) supporting both direct upload and YouTube URLs. |
| **Session 4** | 17:30 – 19:30 | Biomechanical Studio (`/jobs/:jobId`): Native HTML5 video player, 3D computer vision skeleton overlay, rep-by-rep timeline, safe timestamp seeking, and biomechanical fault diagnostics with AI cues. |
| **Session 5** | 20:00 – 21:30 | Multi-state testing (Completed, Processing 68%, Queued #2, Failed Occlusion), `AI_USAGE.md` compilation, `docs/ADR.md` architecture justification, Dockerfile + CI/CD workflows, and build verification. |

---

## Live URL Acceptance Criteria Verification

1. **Acceptance 1 (Rep Count Verification):**
   - Log in via Google or Email demo.
   - View Session #883 (Squat) or submit a new workout.
   - Confirm verified rep count (12 reps: 10 clean, 2 flagged deviations) matches manual inspection.
2. **Acceptance 2 (Flagged Rep Seek):**
   - On the `/jobs/:jobId` analysis studio, click **Rep 02 (Flagged: Knee Cave)** or **Rep 04 (Flagged: Shallow Depth)**.
   - The native HTML5 video player immediately and safely seeks to the exact rep start timestamp (`00:09` / `00:19`), highlighting the joint angle HUD and deviation callout.
3. **Acceptance 3 (Clean Failure on No Person / Occlusion):**
   - Inspect Session #880 (Failed) or switch to the **Failed State** tab.
   - View error diagnostics with explicit code (`ERR_CV_OCCLUSION_DETECTED` / `ERR_CV_NO_PERSON_DETECTED`) displaying frame indices (#142–210) and root causes without app crashes.
4. **Acceptance 4 (User Authorization Isolation):**
   - Attempting to access an unauthorized job ID returns a `403 Forbidden` message (*"You don't have permission to view this workout"*), strictly preventing cross-tenant data leakage.

