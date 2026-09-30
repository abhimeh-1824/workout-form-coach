# Workout Form Coach - Backend

## Purpose
Backend foundation for the Workout Form Coach application. This foundation provides a clean, modular FastAPI architecture with centralized configuration, CORS support, health monitoring, a PostgreSQL database layer using SQLAlchemy 2.x models, schema migrations via Alembic, Google OAuth 2.0 with PKCE, secure server-signed session management, user-authorized job management, and server-side YouTube video ingestion with SSRF protection.

## Tech Stack
- **Python**: 3.12+ (tested with Python 3.13)
- **Framework**: FastAPI
- **ASGI Server**: Uvicorn
- **ORM**: SQLAlchemy 2.x
- **Database Driver**: psycopg 3 (`psycopg[binary]`)
- **Database Migrations**: Alembic
- **Authentication**: Authlib & Google OAuth 2.0 (PKCE)
- **Session Security**: itsdangerous (cryptographically signed HttpOnly cookies)
- **YouTube Ingestion**: yt-dlp
- **Configuration**: Pydantic Settings & python-dotenv
- **Testing**: Pytest & HTTPX (TestClient)

## Project Structure
```text
backend/
├── alembic/
│   ├── versions/
│   │   ├── 7a4a7b799f66_initial_database_setup.py
│   │   └── 4e5cd6446bbf_create_users_jobs_reps_and_reports_.py
│   ├── env.py
│   ├── script.py.mako
│   └── README
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── auth.py
│   │       ├── health.py
│   │       └── jobs.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   └── security.py
│   ├── db/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── session.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── assets/
│   │   │   └── pose_landmarker_lite.task
│   │   ├── user.py
│   │   ├── job.py
│   │   ├── rep.py
│   │   └── report.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── job.py
│   │   ├── rep.py
│   │   ├── report.py
│   │   └── user.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── form_rules.py
│   │   ├── job_queue.py
│   │   ├── joint_angles.py
│   │   ├── landmark_smoother.py
│   │   ├── pose_detector.py
│   │   ├── rep_counter.py
│   │   ├── storage.py
│   │   ├── video.py
│   │   ├── video_annotator.py
│   │   ├── video_processor.py
│   │   ├── workout_analyzer.py
│   │   └── youtube.py
│   └── worker/
│       ├── __init__.py
│       └── worker.py
├── docs/
│   └── ADR.md
├── tests/
│   ├── __init__.py
│   ├── test_auth.py
│   ├── test_db_config.py
│   ├── test_health.py
│   ├── test_job_queue.py
│   ├── test_jobs.py
│   ├── test_models.py
│   ├── test_pose_detector.py
│   ├── test_rep_counter.py
│   ├── test_step14_outputs.py
│   ├── test_video_processor.py
│   ├── test_workout_analyzer.py
│   └── test_youtube.py
├── .env
├── .env.example
├── .gitignore
├── alembic.ini
├── requirements.txt
└── README.md
```

## Setup Instructions

### 1. Prerequisites
- Python 3.12 or newer
- PostgreSQL installed and running locally or via network
- Optional: `ffprobe` / `ffmpeg` for deep video duration probing

### 2. Create and Activate Virtual Environment
Navigate to the `backend/` directory:

On Windows (PowerShell):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

On macOS / Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env`:

On Windows:
```powershell
copy .env.example .env
```

On macOS / Linux:
```bash
cp .env.example .env
```

Default configuration template:
```env
APP_NAME=Workout Form Coach
APP_ENV=development
FRONTEND_URL=http://localhost:5173
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/workout_form_coach

# Google OAuth & Session Security
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/auth/google/callback
SESSION_SECRET=workout_form_coach_dev_session_secret_change_in_production

# Video and Ingestion Settings
MEDIA_ROOT=media
MAX_VIDEO_SIZE_MB=100
MAX_VIDEO_DURATION_SECONDS=60
YOUTUBE_DOWNLOAD_TIMEOUT_SECONDS=120
```

## Authentication & Session Management

### Google OAuth Flow
- Authentication uses Google OAuth 2.0 Authorization Code flow with **PKCE** (`code_challenge_method=S256`).
- Scopes requested: `openid email profile`.
- **Zero Token Persistence**: Neither Google access tokens nor refresh tokens are stored in the database or client cookies.

### Session Security
- Authentication state is tracked using a server-signed, tamper-proof **HttpOnly cookie** (`session`).
- Cookie properties:
  - `HttpOnly`: true (inaccessible to JavaScript / protects against XSS)
  - `Secure`: true in production
  - `SameSite`: Lax
  - `Max-Age`: 7 days (604,800 seconds)
- The cookie payload contains only the user ID signed via HMAC-SHA256 (`SESSION_SECRET`). Client-supplied user IDs are never trusted.

## Jobs API & Authorization

All job management endpoints require an active, authenticated session. Client-supplied user IDs are never accepted; ownership is strictly derived from the server-validated session cookie (`current_user = Depends(get_current_user)`).

### Endpoints
- **`POST /api/v1/jobs`**: Create a new queued analysis job.
  - Allowed `exercise`: `squat`, `pushup`, `lunge`.
  - Allowed `source_type`: `upload`, `youtube`.
  - `source_url` is required when `source_type` is `youtube`, and must not be present when `source_type` is `upload`.
  - Creates the job with `status = "queued"`, `progress = 0`, and `attempts = 0`.
- **`GET /api/v1/jobs`**: Paginated list of jobs belonging **strictly to the authenticated user** (ordered newest first).
  - Supports `limit` (default 20, max 100) and `offset` (default 0).
- **`GET /api/v1/jobs/{job_id}`**: Retrieves metadata and processing status for a single job.
- **`POST /api/v1/jobs/{job_id}/youtube`**: Triggers server-side YouTube ingestion for a queued YouTube job.

### Strict User Authorization & Privacy
- Every database query for job retrieval scopes by both ID and owner:
  ```sql
  SELECT * FROM jobs WHERE id = :job_id AND user_id = :current_user_id;
  ```
- If a job does not exist or belongs to another user, the API returns **HTTP 404 Not Found** (never HTTP 403). This prevents unauthorized actors from discovering or enumerating the existence of other users' jobs.

## YouTube Ingestion & SSRF Protection

### Ingestion Flow (`POST /api/v1/jobs/{job_id}/youtube`)
1. **Ownership Verification**: Scopes job lookup to `current_user.id`.
2. **Pre-Conditions**: Verifies `source_type == "youtube"`, `source_url` exists, and video has not already been ingested.
3. **URL Validation**: Validates YouTube URL syntax and ensures only official YouTube domains are accepted:
   - `https://www.youtube.com/watch?v=VIDEO_ID`
   - `https://youtu.be/VIDEO_ID`
   - `https://www.youtube.com/shorts/VIDEO_ID`
4. **SSRF Defense**:
   - Resolves hostnames via DNS and rejects loopback (`127.0.0.0/8`, `::1`), private RFC1918 subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), link-local / cloud metadata (`169.254.0.0/16`), and internal hostnames (`localhost`, `*.local`).
   - Intercepts all downloader redirects: each redirect destination is validated against SSRF restrictions and Google/YouTube video CDN boundaries (`*.googlevideo.com`).
5. **Metadata Duration Check**: Pre-probes video metadata; if reported duration exceeds 60 seconds, download is halted immediately.
6. **Download to Temporary File**: Streams to an isolated temporary file with a hard size limit (`MAX_VIDEO_SIZE_MB=100`) and hard timeout (`YOUTUBE_DOWNLOAD_TIMEOUT_SECONDS=120`).
7. **Post-Download Verification**: Verifies container header, actual file size, and true duration (`MAX_VIDEO_DURATION_SECONDS=60`).
8. **Storage Commitment**: Moves file to `media/jobs/{job_id}/original.mp4` and sets `job.video_path`. The job remains in `queued` status (`progress=0`).

### Cloud Environment Limitation & Upload Fallback
Automated server-side YouTube downloads may occasionally be restricted or blocked by YouTube in datacenter/cloud environments (e.g., bot detection or sign-in walls). When this occurs, the API returns a structured error instructing the user to use the direct video upload option (`source_type: "upload"`).

## Database Schema & Relationships

### Entity Relationships
- **User 1 ──── N Jobs**: A user owns multiple workout analysis jobs. Deleting a user cascades and deletes their jobs.
- **Job 1 ──── N Reps**: A job contains granular timestamp and metric records for each detected repetition. Deleting a job cascades and deletes its reps.
- **Job 1 ──── 1 Report**: A job produces a single aggregated summary report. Enforced via a unique constraint on `reports.job_id`. Deleting a job cascades and deletes its report.

### Justified Index
- **`ix_jobs_status_created_at`** on `jobs(status, created_at)`:
  - **Justification**: Background workers poll for pending jobs ready to be processed using:
    ```sql
    SELECT * FROM jobs
    WHERE status = 'queued'
    ORDER BY created_at ASC
    LIMIT 1 FOR UPDATE SKIP LOCKED;
    ```
    This composite index allows workers to immediately locate queued jobs and fetch the oldest submissions in strict FIFO order without full-table sequential scans or expensive filesorts.

## Database Setup

1. **PostgreSQL Service**: Ensure PostgreSQL is running.
2. **Create Database**: Create the `workout_form_coach` database:
   ```sql
   CREATE DATABASE workout_form_coach;
   ```
3. **Configure Connection**: Verify `DATABASE_URL` in `.env` has your PostgreSQL credentials.
4. **Run Migrations**: Apply database migrations to head:
   ```bash
   alembic upgrade head
   ```
5. **Check Current Revision**:
   ```bash
   alembic current
   ```

## Running the Development Server
From the `backend/` directory, start the server using Uvicorn:

```bash
python -m uvicorn app.main:app --reload
```

The server will start at: `http://localhost:8000`

## Running the Background Job Worker
From the `backend/` directory, start the queue worker process:

```bash
python -m app.worker.worker
```

### Worker Architecture & Concurrency Control
- **Source of Truth**: The PostgreSQL `jobs` table serves directly as the durable queue. No Redis, Celery, or external brokers are required.
- **Safe Claiming**: Uses SQLAlchemy with `SELECT ... FOR UPDATE SKIP LOCKED` inside an atomic transaction. This guarantees that multiple concurrent worker processes never claim the same job.
- **Fair Ordering**: Jobs are claimed in strict FIFO order (`ORDER BY created_at ASC`).
- **State Machine**: Transitions status atomically from `queued` to `processing`, records `started_at`, and increments the `attempts` counter.
- **Transaction Safety**: Video processing executes completely outside long-lived database transactions. Short, atomic transactions are used strictly for claiming, persisting intermediate progress, and finalizing status (`completed` / `failed`).
- **Incremental Frame Streaming**: Streams frames one-by-one with OpenCV (`cap.grab()` and selective `cap.retrieve()`) at configurable `PROCESSING_FPS` (default: 15). Zero full-video memory buffering.
- **Progress Tracking**: Monotonically advances `job.progress` from 0 to 100 based on actual decoded frame timestamps, writing to PostgreSQL only on meaningful increments (>= 5%) and reaching 100% strictly upon completion.
- **Failure Isolation**: Missing, corrupt, or empty video files transition safely to `failed` with clean, human-readable error messages while detailed tracebacks are logged server-side. The worker loop continues uninterrupted.
- **Polling Loop**: When the queue is empty, the worker sleeps for `WORKER_POLL_INTERVAL_SECONDS` (default: 2.0s) without aggressive busy-waiting.
- **Graceful Shutdown**: Listens for OS termination signals (`SIGINT`, `SIGTERM`) to stop cleanly.

## Pose Detection (MediaPipe Pose)
- **Model Architecture**: Uses Google's MediaPipe Pose (`mediapipe.tasks.python.vision.PoseLandmarker`) backed by `pose_landmarker_lite.task` running on CPU with XNNPACK acceleration.
- **33 Landmark Keypoint Extraction**: For every sampled frame, extracts all 33 standardized body landmarks:
  - Normalized Coordinates: `x` (horizontal), `y` (vertical), `z` (relative depth).
  - Landmark Visibility: Confidence score ($0.0 \le v \le 1.0$) preserved for downstream joint reliability filtering.
  - Official Naming: Mapped programmatically via MediaPipe's `PoseLandmark` enum (NOSE, SHOULDERS, ELBOWS, WRISTS, HIPS, KNEES, ANKLES, etc.).
- **Sequential Video Tracking**: Runs in `RunningMode.VIDEO` mode with monotonic frame timestamps (`timestamp_ms`), maintaining temporal tracking across frames for high throughput.
- **Single-Person Assumption**: Configured with `num_poses = 1` for individual workout form tracking. If multiple individuals are visible, MediaPipe focuses on the primary subject.
- **Missing Pose Handling**: Frames without a detectable person return `pose_detected = False` and an empty landmark array without aborting processing.
- **No-Person Policy**: Videos with zero detected human poses across all sampled frames fail safely with `"No person detected in the video."`
- **Decoupled Design**: The pose estimation layer is strictly isolated from exercise state machines, joint angle geometry, rep counting, and form scoring.

## Biomechanics Layer (Smoothing & Joint Angles)

### 1. Landmark Smoothing
- **Method**: Exponential Moving Average (EMA):
  $$S_t = \alpha X_t + (1 - \alpha) S_{t-1}$$
- **Configured Parameter**: `LANDMARK_SMOOTHING_ALPHA = 0.5` (configurable via environment).
- **Rationale**: Real-time neural pose extractors like MediaPipe inherently exhibit frame-to-frame coordinate jitter and micro-fluctuations even when the human subject is completely stationary. Smoothing stabilizes coordinate trajectories for accurate joint angle computation without the computational latency of complex Kalman filters or ML models.
- **Rules**:
  - Smooths normalized spatial coordinates $(x, y, z)$.
  - Landmark names are preserved unchanged.
  - Raw landmark `visibility` confidence is preserved separately without synthetic values.
  - Missing landmarks or undetected frames safely reset state to prevent erratic velocity leaps upon reappearance.
  - Session-scoped: instantiated freshly per video processing session with zero cross-video state leaks.

### 2. Joint Angle Calculation
- **Generic 3-Point Angle Calculation**:
  $$\theta = \arccos\left(\text{clamp}\left(\frac{\vec{BA} \cdot \vec{BC}}{|\vec{BA}| \cdot |\vec{BC}|}, -1.0, 1.0\right)\right)$$
  Calculated at vertex $B$ between vectors $\vec{BA}$ and $\vec{BC}$, yielding an interior angle between $0^\circ$ and $180^\circ$.
- **Coordinate Space**: Evaluated in normalized 2D space $(x, y)$. Normalized 2D coordinates are scale- and translation-invariant across camera distances, and avoid noisy depth ($z$) estimation artifacts for planar workout movements.
- **Required Joints**:
  - `left_elbow`: LEFT_SHOULDER $\to$ LEFT_ELBOW $\to$ LEFT_WRIST
  - `right_elbow`: RIGHT_SHOULDER $\to$ RIGHT_ELBOW $\to$ RIGHT_WRIST
  - `left_knee`: LEFT_HIP $\to$ LEFT_KNEE $\to$ LEFT_ANKLE
  - `right_knee`: RIGHT_HIP $\to$ RIGHT_KNEE $\to$ RIGHT_ANKLE
  - `left_hip`: LEFT_SHOULDER $\to$ LEFT_HIP $\to$ LEFT_KNEE
  - `right_hip`: RIGHT_SHOULDER $\to$ RIGHT_HIP $\to$ RIGHT_KNEE
  - `left_shoulder`: LEFT_HIP $\to$ LEFT_SHOULDER $\to$ LEFT_ELBOW
  - `right_shoulder`: RIGHT_HIP $\to$ RIGHT_SHOULDER $\to$ RIGHT_ELBOW
- **Visibility Threshold**: `LANDMARK_VISIBILITY_THRESHOLD = 0.5`. If any of the 3 points has visibility confidence $< 0.5$, the angle returns `null`.
- **Degenerate & Missing Handling**:
  - Degenerate vectors ($A = B$ or $C = B$) return `null` instead of causing division by zero.
  - Missing or occluded landmarks return `null`, never $0^\circ$ (which would erroneously register as extreme joint flexion in rep counting).
  - Floating-point clamping prevents numerical domain errors in $\arccos$.

## Exercise Repetition Counting
Rep counting uses an explicit two-state finite state machine (`UP` $\leftrightarrow$ `DOWN`) driven by smoothed joint angles:
- **Hysteresis Thresholds**:
  - Squat: `UP >= 160°`, `DOWN <= 100°` (bilateral knees)
  - Push-up: `UP >= 160°`, `DOWN <= 90°` (bilateral elbows)
  - Lunge: `UP >= 150°`, `DOWN <= 100°` (active knee)
- **State Invariants**: Transition from `UP` to `DOWN` initiates repetition tracking. Completion requires transitioning back to `UP`. Repeated frames in the same position do not duplicate counts.
- **Asymmetry Tracking**: Tracks bilateral joint difference during movement for form evaluation.

## Workout Analysis (ROM, Tempo, Form Rules & Form Score)

The Workout Analysis service evaluates biomechanical quality for every completed repetition and computes workout-level aggregate metrics.

> **CRITICAL NOTE ON METHODOLOGY**:
> Form analysis in this system is strictly **deterministic and rule-based**, derived from established biomechanical thresholds. It does **NOT** rely on probabilistic LLM/AI evaluations or non-reproducible black-box scoring.

### 1. Range of Motion (ROM)
- **Definition**: The angular range traversed by the primary joint during a completed repetition:
  $$\text{ROM} = \text{max\_angle} - \text{min\_angle}$$
- **Primary Exercise Joints**:
  - **Squat**: Bilateral knee angles. When both knees are visible: $(\theta_{\text{left}} + \theta_{\text{right}}) / 2$. When one knee is occluded, uses the single visible knee.
  - **Push-up**: Bilateral elbow angles. Uses average of visible elbows, or the single visible elbow if one side is occluded.
  - **Lunge**: Active knee angle. The active leg is determined by lowest angle reached during descent. Trailing knee data is not averaged into active knee ROM.
- **Missing Data Handling**: If angle measurements are missing or invalid, $\text{ROM} = \text{null}$. Missing data is never substituted with $0^\circ$. Negative values are mathematically clamped to $0.0^\circ$. Values are rounded to 1 decimal place.

### 2. Tempo Calculation
- **Definition**: Repetition duration evaluated strictly across the video timeline:
  $$\text{tempo} = t_{\text{end}} - t_{\text{start}}$$
- **Units**: Evaluated in seconds and rounded to 2 decimal places.
- **Missing / Invalid Handling**: If timestamps are missing or invalid ($t_{\text{end}} < t_{\text{start}}$), $\text{tempo} = \text{null}$. Tempo is never calculated from wall-clock worker processing time.

### 3. Exercise-Specific Form Rules
Rules produce structured, explainable feedback objects (`code`, `message`, `severity`):

#### A. Squats
- **`INSUFFICIENT_DEPTH`** (`severity: warning`): Triggered when minimum knee angle during the repetition fails to reach the depth threshold ($\text{min\_angle} > 100.0^\circ$, configured via `SQUAT_DEPTH_ANGLE`).
- **`KNEE_ASYMMETRY`** (`severity: warning`): Triggered when bilateral knee difference exceeds the threshold ($\max |\theta_{\text{left}} - \theta_{\text{right}}| > 15.0^\circ$, configured via `KNEE_ASYMMETRY_THRESHOLD`).

#### B. Push-ups
- **`INSUFFICIENT_DEPTH`** (`severity: warning`): Triggered when minimum elbow angle fails to reach depth threshold ($\text{min\_angle} > 90.0^\circ$, configured via `PUSHUP_DEPTH_ANGLE`).
- **`ELBOW_ASYMMETRY`** (`severity: warning`): Triggered when bilateral elbow angle difference exceeds threshold ($\max |\theta_{\text{left}} - \theta_{\text{right}}| > 15.0^\circ$, configured via `ELBOW_ASYMMETRY_THRESHOLD`).

#### C. Lunges
- **`INSUFFICIENT_DEPTH`** (`severity: warning`): Triggered when the active knee fails to reach the depth threshold ($\text{min\_angle} > 100.0^\circ$, configured via `LUNGE_DEPTH_ANGLE`).
- **`LUNGE_ASYMMETRY`** (`severity: warning`): Triggered when bilateral knee difference exceeds threshold ($\max |\theta_{\text{left}} - \theta_{\text{right}}| > 15.0^\circ$, configured via `LUNGE_ASYMMETRY_THRESHOLD`).

### 4. Handling of Missing Landmarks (Avoiding False Positives)
Missing landmarks, low visibility scores ($< 0.5$), or single-sided camera angles represent **insufficient evidence**, not bad form:
- Asymmetry rules are evaluated **only** when bilateral joint data is available. If only one knee or elbow is visible, no asymmetry issue is created.
- Missing trailing leg data in lunges is not flagged as a form failure.
- Repetitions with missing angle data do not receive artificial form penalties.

### 5. Form Score Calculation
- **Base Score**: Repetition score starts at $100.0$.
- **Deduction Policy**:
  - `warning` issue: $-10.0$ points (configurable via `FORM_WARNING_PENALTY`).
  - `major` issue: $-20.0$ points (configurable via `FORM_MAJOR_PENALTY`).
- **Bounding**: Final score is clamped to $[0.0, 100.0]$.
- **Explainability**: Score deductions map directly 1:1 to detected issues without arbitrary weighting.

### 6. Workout-Level Aggregate Metrics
Aggregates are calculated across all completed repetitions in the workout session:
- **`total_reps`**: Count of completed repetitions detected.
- **`average_rom`**: Arithmetic mean of valid repetition ROM values (excluding `null` values; missing measurements are not averaged as zero).
- **`average_tempo`**: Arithmetic mean of valid repetition tempos (excluding `null` values).
- **`average_score`**: Arithmetic mean of repetition form scores.
- When no repetitions are detected, all averages safely return `null`.


## Processed Video & Workout Output Layer

The output layer finalizes video processing by producing annotated videos, persisting transactional results to PostgreSQL, and exposing secure authenticated REST APIs.

### 1. Processed Video Generation
- **Single-Pass Rendering**: Annotated frames are written directly to `cv2.VideoWriter` during the existing frame-by-frame processing pass, completely avoiding redundant pose inference or second-pass decoding loops.
- **Skeleton Overlay**: Renders all 33 MediaPipe body landmarks and 35 anatomical connection lines directly over original video frames. Occluded joints ($v < 0.5$) are excluded to prevent misleading connections.
- **Rep Counter HUD**: Overlays a semi-transparent HUD banner in the top corner displaying the real-time repetition counter (`REPS: <count>`), exercise name, and form score.
- **Resolution & Aspect Preservation**: Preserves original video dimensions without letterboxing or distortion.
- **Error Cleanup**: Incomplete or corrupt video files are automatically unlinked and cleaned from storage if processing encounters an error.

### 2. Transaction-Safe Database Persistence & Idempotency
- **Atomic Persistence**: Repetition records (`Rep`), summary report (`Report`), and final job state (`Job.status = COMPLETED`, `progress = 100`, `processed_video_path = ...`) are committed inside a single atomic database transaction.
- **Idempotency Guarantee**: If a job is retried or reprocessed, any prior `Rep` and `Report` records for that `job_id` are deleted before new records are inserted. This guarantees that retries never produce duplicate rows or violating unique constraints (`uq_reps_job_id_rep_number`, `uq_reports_job_id`).
- **Failure Isolation**: If rendering or database insertion fails, the transaction is rolled back, the job is marked `FAILED` with a descriptive message, and no partial data remains in the database.

### 3. Secure Processed Video Streaming
- **Authentication**: Requires an active, authenticated user session.
- **Ownership Authorization**: Only the user who created the job can stream its processed video. Requests by other users return `404 Not Found` (preventing user enumeration).
- **Path Traversal Protection**: Output paths are validated against `MEDIA_ROOT` (`is_relative_to(media_root)`); arbitrary filesystem access is strictly blocked.

## Endpoints Summary

> For complete, endpoint-by-endpoint frontend integration specifications including JSON schemas, payload examples, error codes, and step-by-step upload/YouTube flows, see [API_README.md](API_README.md).

- **Root Welcome**: `GET http://localhost:8000/`
- **Application Health Check**: `GET http://localhost:8000/api/v1/health`
- **Google OAuth Login**: `GET http://localhost:8000/api/v1/auth/google/login`
- **Google OAuth Callback**: `GET http://localhost:8000/api/v1/auth/google/callback`
- **Current User Profile**: `GET http://localhost:8000/api/v1/auth/me`
- **Logout Session**: `POST http://localhost:8000/api/v1/auth/logout`
- **Create Job**: `POST http://localhost:8000/api/v1/jobs`
- **List User Jobs**: `GET http://localhost:8000/api/v1/jobs`
- **Get Job Details**: `GET http://localhost:8000/api/v1/jobs/{job_id}`
- **Ingest YouTube Video**: `POST http://localhost:8000/api/v1/jobs/{job_id}/youtube`
- **Get Completed Reps**: `GET http://localhost:8000/api/v1/jobs/{job_id}/reps`
- **Get Workout Report**: `GET http://localhost:8000/api/v1/jobs/{job_id}/report`
- **Stream Processed Video**: `GET http://localhost:8000/api/v1/jobs/{job_id}/video`

## Interactive API Documentation
- **API Integration Reference**: [API_README.md](API_README.md)
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

## Running Tests
Run the test suite from the `backend/` directory:

```bash
pytest
```

