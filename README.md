# 🏋️ Workout Form Coach

> **AI-Powered Biomechanical Vision & Kinematics Analysis Platform**  
> Real-time pose estimation, repetition counting, range of motion (ROM) tracking, and rule-based form evaluation for athletic movements.

---

## 📌 Table of Contents

- [What is Workout Form Coach?](#-what-is-workout-form-coach)
- [Core Features](#-core-features)
- [System Architecture](#-system-architecture)
- [Repository Structure](#-repository-structure)
- [Prerequisites](#-prerequisites)
- [How to Run the Project](#-how-to-run-the-project)
  - [Option A: Full-Stack Run (Backend + Worker + Frontend)](#option-a-full-stack-run-recommended)
  - [Option B: Frontend-Only Quickstart (Mock Mode)](#option-b-frontend-only-quickstart-mock-mode)
  - [Option C: Docker Deployment](#option-c-docker-deployment)
- [Supported Exercises & Biomechanical Rules](#-supported-exercises--biomechanical-rules)
- [Form Scoring Methodology](#-form-scoring-methodology)
- [API Endpoints Summary](#-api-endpoints-summary)
- [Running Tests & Quality Assurance](#-running-tests--quality-assurance)
- [Environment Configuration](#-environment-configuration)

---

## 💡 What is Workout Form Coach?

**Workout Form Coach** is an end-to-end computer vision and biomechanics platform built for athletes, trainers, and physical therapists. While typical fitness apps only count repetitions or log weights, Workout Form Coach actively evaluates **movement quality**, **joint kinematics**, and **injury risk factors**.

Athletes upload recorded workout clips (or submit YouTube video links) of **Squats**, **Push-ups**, or **Lunges**. The platform processes the video through a high-performance vision pipeline, extracts anatomical keypoints, runs deterministic biomechanical evaluation models, and renders an interactive **Kinematics Studio** featuring:

1. **Rep-by-rep breakdown:** Exact timestamps, range of motion (ROM), cadence tempo, and form flags.
2. **Interactive video player:** 33-landmark skeleton overlay with real-time HUD rep counters and safe timeline scrubbing to flagged deviations.
3. **Deterministic fault diagnosis:** Precise coaching cues (e.g., *Insufficient Depth*, *Knee Asymmetry*, *Elbow Flare*) without subjective or hallucinatory black-box AI scores.
4. **Aggregate session analytics:** Biomechanical form score (0–100), stability metrics, and kinematic trajectory graphs.

---

## ✨ Core Features

### 1. Computer Vision & Biomechanics Pipeline
- **MediaPipe Pose (33 3D Keypoints):** High-speed body landmark extraction running locally on CPU with XNNPACK acceleration.
- **Temporal Landmark Smoothing:** Exponential Moving Average (EMA, $\alpha = 0.5$) coordinate stabilization eliminating high-frequency sensor jitter.
- **Normalized 2D Joint Angles:** Scale- and camera-distance invariant trigonometric angle calculations for elbows, knees, hips, and shoulders with visibility confidence gating ($\ge 0.5$).
- **Finite State Machine Rep Counter:** Bilateral joint angle hysteresis (`UP` $\leftrightarrow$ `DOWN`) preventing false triggers at apex and nadir.
- **Video HUD & Skeleton Overlay:** Single-pass OpenCV rendering overlaying anatomical wireframes and real-time rep counter banners.

### 2. Reliable Asynchronous Architecture
- **Durable PostgreSQL Queue:** Direct database-backed queue using `SELECT ... FOR UPDATE SKIP LOCKED` for atomic FIFO job claiming without Redis/Celery dependencies.
- **Decoupled Worker Processing:** Memory-safe OpenCV frame streaming (15 FPS target) updating job progress monotonically in PostgreSQL.
- **Failure Isolation:** Automatically handles corrupted media, invalid formats, or videos with no visible person, returning explicit, human-readable diagnostics.

### 3. Enterprise-Grade Security
- **Google OAuth 2.0 with PKCE:** Secure authorization code flow without token persistence in database or cookies.
- **HttpOnly Signed Sessions:** Tamper-proof server-side HMAC session cookies (`itsdangerous`) protecting against XSS and session hijacking.
- **Strict Multi-Tenant Privacy:** Scoped database queries returning HTTP 404 on cross-tenant access to prevent enumeration attacks.
- **SSRF Defense Engine:** DNS validation, private IP blocking (RFC 1918, link-local, loopback), and Google CDN boundary verification for YouTube ingestion.

### 4. Modern Kinematics Studio Frontend
- **Built with React 19, Vite & Tailwind CSS v4:** High-refresh interface using Space Grotesk, Plus Jakarta Sans, and JetBrains Mono typography.
- **Interactive Rep Scrubbing:** Clicking any flagged repetition card seeks the video player directly to that rep's initiation timestamp.
- **Zero-Dependency Mock Mode:** Switch between live FastAPI backend and built-in mock simulation with a single environment flag (`VITE_USE_MOCK_API`).

---

## 🏗️ System Architecture

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        React 19 Frontend (Vite)                       │
│  - Dashboard & Workout Metrics       - Video Player & Skeleton HUD     │
│  - Direct Upload & YouTube Ingest    - Rep-by-Rep Kinematics Timeline  │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │ HTTP (REST + HttpOnly Cookies)
                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│                         FastAPI Backend API                            │
│  - Google OAuth 2.0 (PKCE)           - Signed Session Auth             │
│  - SSRF-Protected YouTube Ingestion  - Job Creation & Status Polling   │
│  - Video Streaming Endpoint          - Repetition & Report Data APIs   │
└──────────────────┬─────────────────────────────────┬───────────────────┘
                   │                                 │
                   ▼                                 ▼
┌─────────────────────────────────────┐  ┌───────────────────────────────┐
│       PostgreSQL Database           │  │      Local Media Storage      │
│  - users, jobs, reps, reports       │  │  - media/jobs/{job_id}/...    │
│  - FIFO Queue (SKIP LOCKED)         │  │    original.mp4 & annotated   │
└──────────────────▲──────────────────┘  └───────────────▲───────────────┘
                   │                                     │
                   └─────────────────┬───────────────────┘
                                     │
┌────────────────────────────────────┴───────────────────────────────────┐
│                     Background Job Worker Process                      │
│  1. Atomic Claim (FOR UPDATE SKIP LOCKED)                              │
│  2. Frame Extraction & MediaPipe 33-Landmark Pose Estimation           │
│  3. EMA Coordinate Smoothing & Joint Angle Geometry Calculations       │
│  4. Two-State Rep Counter & Deterministic Biomechanical Rule Engine    │
│  5. Annotated Video Synthesis (OpenCV Overlay & Rep HUD Banner)        │
│  6. Atomic Database Persistence (Reps, Summary Report, Status 100%)    │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 📁 Repository Structure

```text
workout-form-coach/
├── README.md                   # Top-level project guide & run instructions (this file)
├── AI_USAGE.md                 # Documentation of AI assistance, reviews, and bug fixes
│
├── backend/                    # FastAPI Application & Background Worker
│   ├── app/
│   │   ├── api/                # FastAPI routes (auth, health, jobs) & dependencies
│   │   ├── core/               # App configuration (pydantic-settings) & security
│   │   ├── db/                 # SQLAlchemy 2.x engine, declarative base & sessions
│   │   ├── models/             # ORM models (User, Job, Rep, Report) & pose assets
│   │   ├── schemas/            # Pydantic validation schemas
│   │   ├── services/           # Pose detection, joint angles, rep counter, analyzer
│   │   └── worker/             # Asynchronous background video processing worker
│   ├── alembic/                # Alembic migration scripts
│   ├── tests/                  # Pytest test suite (unit, integration & pipeline)
│   ├── media/                  # Video storage directory (created at runtime)
│   ├── requirements.txt        # Python backend dependencies
│   ├── alembic.ini             # Alembic migration configuration
│   ├── API_README.md           # Exhaustive REST API contract & JSON schemas
│   └── README.md               # Backend-specific architecture documentation
│
└── frontend/                   # React 19 + Vite Single Page Application
    ├── src/
    │   ├── app/                # App entrypoint & React Router routes
    │   ├── components/         # Analysis studio, video player, jobs, auth components
    │   ├── context/            # AuthContext (session state & login/logout)
    │   ├── hooks/              # Custom hooks (useJobs, useJobStatus, useAuth)
    │   ├── pages/              # Dashboard, JobDetails, Login, SubmitWorkout pages
    │   ├── services/           # Centralized apiClient, API endpoints, mock data
    │   └── utils/              # Validators, formatters, and constants
    ├── package.json            # Node.js dependencies & scripts
    ├── vite.config.ts          # Vite configuration
    ├── docker-compose.yml      # Docker compose configuration for frontend
    └── README.md               # Frontend-specific architecture documentation
```

---

## ⚙️ Prerequisites

Ensure you have the following installed on your machine:

| Component | Minimum Version | Notes |
|---|---|---|
| **Python** | `3.12+` (tested on 3.13) | Backend API & Queue Worker |
| **Node.js** | `18.x` or `20.x+` (npm / bun) | Frontend React 19 app |
| **PostgreSQL** | `14+` or `16+` | Relational database & durable queue |
| **ffmpeg / ffprobe** | *Optional* | Enhanced video probing & validation |

---

## 🚀 How to Run the Project

### Option A: Full-Stack Run (Recommended)

Follow these steps to run the complete system with the real database, FastAPI backend, background worker, and React frontend.

#### Step 1: Clone the Repository
```bash
git clone https://github.com/abhisekh-behera/workout-form-coach.git
cd workout-form-coach
```

---

#### Step 2: Set Up the PostgreSQL Database
Make sure PostgreSQL is running, then create the database:

```sql
CREATE DATABASE workout_form_coach;
```

---

#### Step 3: Set Up and Run the Backend

1. **Navigate to the backend directory:**
   ```bash
   cd backend
   ```

2. **Create and activate a Python virtual environment:**
   - **On Windows (PowerShell):**
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     ```
   - **On macOS / Linux:**
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   Copy the example environment configuration:
   - **Windows:** `copy .env.example .env`
   - **macOS / Linux:** `cp .env.example .env`

   Edit `.env` to verify your PostgreSQL credentials:
   ```env
   DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/workout_form_coach
   FRONTEND_URL=http://localhost:3000
   SESSION_SECRET=a_very_secret_and_secure_random_string_32_chars
   ```

5. **Run database migrations:**
   ```bash
   alembic upgrade head
   ```

6. **Start the FastAPI development server:**
   ```bash
   python -m uvicorn app.main:app --reload --port 8000
   ```
   > 🌐 The Backend API is now live at: **`http://localhost:8000`**  
   > 📖 Swagger interactive docs: **`http://localhost:8000/docs`**

---

#### Step 4: Run the Background Queue Worker

In a **separate terminal window** (with the backend `.venv` activated):

```bash
cd backend
# Windows: .\.venv\Scripts\Activate.ps1 | Linux/macOS: source .venv/bin/activate
python -m app.worker.worker
```
> ⚡ The worker will begin polling PostgreSQL for queued workout jobs.

---

#### Step 5: Set Up and Run the Frontend

In another **new terminal window**:

1. **Navigate to the frontend directory:**
   ```bash
   cd frontend
   ```

2. **Install Node dependencies:**
   ```bash
   npm install
   ```

3. **Configure environment variables:**
   Create a `.env` file (or copy `.env.example`):
   ```env
   VITE_API_BASE_URL=http://localhost:8000
   VITE_USE_MOCK_API=false
   ```
   *(Setting `VITE_USE_MOCK_API=false` ensures the frontend connects directly to your live FastAPI backend).*

4. **Start the frontend development server:**
   ```bash
   npm run dev
   ```
   > 🚀 The web application is now running at: **`http://localhost:3000`**

---

### Option B: Frontend-Only Quickstart (Mock Mode)

If you want to immediately explore the UI, test video playback, review rep timelines, and inspect kinematics graphs **without installing Python or configuring PostgreSQL**, run the frontend in mock mode:

```bash
cd frontend
npm install
```

Create or edit `frontend/.env`:
```env
VITE_USE_MOCK_API=true
```

Start the Vite server:
```bash
npm run dev
```

Visit **`http://localhost:3000`**.  
- All workouts, status transitions (`queued` $\to$ `processing` $\to$ `completed`), rep breakdowns, and failure states are simulated natively in the browser with realistic biomechanical data.

---

### Option C: Docker Deployment

To launch the containerized frontend:

```bash
cd frontend
docker compose up --build
```
The production NGINX-served frontend will be available at **`http://localhost:3000`** with `/health` monitoring active.

---

## 📐 Supported Exercises & Biomechanical Rules

Form analysis is strictly **deterministic and rule-based**, derived from physical joint angles rather than probabilistic AI evaluations.

| Exercise | Primary Joint(s) | State Machine Thresholds | Biomechanical Fault Rules | Detection Criteria | Severity |
|---|---|---|---|---|---|
| **Squat** | Bilateral Knees (`left_knee`, `right_knee`) | `UP >= 160°`<br>`DOWN <= 100°` | **Insufficient Depth** (`INSUFFICIENT_DEPTH`)<br>**Knee Asymmetry** (`KNEE_ASYMMETRY`) | Lowest knee angle $> 100.0^\circ$<br>Bilateral difference $> 15.0^\circ$ | Warning (-10 pts)<br>Warning (-10 pts) |
| **Push-up** | Bilateral Elbows (`left_elbow`, `right_elbow`) | `UP >= 160°`<br>`DOWN <= 90°` | **Insufficient Depth** (`INSUFFICIENT_DEPTH`)<br>**Elbow Asymmetry** (`ELBOW_ASYMMETRY`) | Lowest elbow angle $> 90.0^\circ$<br>Bilateral difference $> 15.0^\circ$ | Warning (-10 pts)<br>Warning (-10 pts) |
| **Lunge** | Active Leg Knee (`left_knee` or `right_knee`) | `UP >= 150°`<br>`DOWN <= 100°` | **Insufficient Depth** (`INSUFFICIENT_DEPTH`)<br>**Lunge Asymmetry** (`LUNGE_ASYMMETRY`) | Active knee lowest angle $> 100.0^\circ$<br>Bilateral difference $> 15.0^\circ$ | Warning (-10 pts)<br>Warning (-10 pts) |

### Occlusion & Insufficient Data Protection
- Asymmetry rules are evaluated **only** when bilateral joints have sufficient visibility ($\ge 0.5$).
- Missing or occluded joints are treated as **insufficient evidence**, never penalized as bad form.
- Degenerate joint configurations return `null` instead of generating mathematical division-by-zero errors.

---

## 📊 Form Scoring Methodology

- **Base Repetition Score:** Starts at **`100.0` points**.
- **Rule Deductions:**
  - `warning` severity deduction: **`-10.0` points** per violation.
  - `major` severity deduction: **`-20.0` points** per violation.
- **Clamping:** Repetition score is strictly bounded to the $[0.0, 100.0]$ range.
- **Session Form Score:** Arithmetic mean of all completed repetition scores:
  $$\text{Average Score} = \frac{1}{N} \sum_{i=1}^{N} \text{Score}_i$$
- **Range of Motion (ROM):** Maximum joint extension angle minus minimum flexion angle during repetition cycle ($\text{max\_angle} - \text{min\_angle}$).
- **Tempo:** Duration in seconds from repetition initiation to completion ($t_{\text{end}} - t_{\text{start}}$).

---

## 🔌 API Endpoints Summary

| Method | Endpoint | Description | Auth Required |
|---|---|---|:---:|
| `GET` | `/` | Root API welcome message | No |
| `GET` | `/api/v1/health` | Service health status check | No |
| `GET` | `/api/v1/auth/google/login` | Initiate Google OAuth 2.0 PKCE flow | No |
| `GET` | `/api/v1/auth/google/callback` | OAuth redirect callback handler | No |
| `GET` | `/api/v1/auth/me` | Retrieve authenticated user profile | **Yes** |
| `POST` | `/api/v1/auth/logout` | Terminate session and clear cookie | **Yes** |
| `POST` | `/api/v1/jobs` | Submit new analysis job (`upload` or `youtube`) | **Yes** |
| `GET` | `/api/v1/jobs` | List user's workout jobs (paginated) | **Yes** |
| `GET` | `/api/v1/jobs/{job_id}` | Poll job processing status & metadata | **Yes** |
| `POST` | `/api/v1/jobs/{job_id}/youtube` | Trigger SSRF-protected YouTube ingestion | **Yes** |
| `GET` | `/api/v1/jobs/{job_id}/reps` | Fetch rep-by-rep kinematics telemetry | **Yes** |
| `GET` | `/api/v1/jobs/{job_id}/report` | Retrieve completed workout summary report | **Yes** |
| `GET` | `/api/v1/jobs/{job_id}/video` | Stream processed video with skeleton HUD overlay | **Yes** |

> For comprehensive endpoint schemas, error codes, and payload examples, refer to [backend/API_README.md](backend/API_README.md).

---

## 🧪 Running Tests & Quality Assurance

### Backend Test Suite
The backend contains comprehensive unit, integration, and end-to-end tests covering models, video processing, rep counting, and authentication:

```bash
cd backend
# Make sure virtual environment is active
pytest
```

To run tests with detailed verbosity:
```bash
pytest -v -s
```

### Frontend Verification
To verify TypeScript types and build optimization:

```bash
cd frontend
# Check TypeScript types
npm run lint

# Verify production build bundle
npm run build
```

---

## 🔧 Environment Configuration

### Backend (`backend/.env`)
| Variable | Default Value | Description |
|---|---|---|
| `APP_NAME` | `Workout Form Coach` | Application title |
| `APP_ENV` | `development` | Runtime environment (`development` / `production`) |
| `FRONTEND_URL` | `http://localhost:3000` | Allowed CORS origin for frontend |
| `DATABASE_URL` | `postgresql+psycopg://...` | PostgreSQL connection string |
| `SESSION_SECRET` | *(Random String)* | HMAC key for signing HttpOnly session cookies |
| `MEDIA_ROOT` | `media` | Filesystem path for ingested and rendered videos |
| `MAX_VIDEO_SIZE_MB` | `100` | Maximum uploaded video file size |
| `MAX_VIDEO_DURATION_SECONDS`| `60` | Maximum video duration allowed for processing |
| `PROCESSING_FPS` | `15` | Frame rate at which the worker samples video |
| `WORKER_POLL_INTERVAL_SECONDS` | `2` | Polling frequency for the queue worker |

### Frontend (`frontend/.env`)
| Variable | Default Value | Description |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8000` | Target URL for backend FastAPI service |
| `VITE_USE_MOCK_API` | `false` | Set to `true` for frontend mock mode (no backend needed) |

---

## 📜 License

This project was developed as a technical assessment for **FalcRise**. All rights reserved.