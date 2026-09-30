# Workout Form Coach — Backend API Documentation

This document serves as the comprehensive integration reference for the **Workout Form Coach** backend REST API. It details all available endpoints, authentication mechanisms, request/response schemas, status codes, and the recommended frontend user workflows.

---

## General Information

- **Base URL (Local Development)**: `http://localhost:8000`
- **API Version Prefix**: `/api/v1`
- **Full Base URL**: `http://localhost:8000/api/v1`
- **Interactive Documentation**:
  - Swagger UI: `http://localhost:8000/docs`
  - ReDoc: `http://localhost:8000/redoc`

---

## Authentication & Session Management

The backend employs **Google OAuth 2.0 with PKCE** and **server-signed HttpOnly session cookies**.

### Cookie Specification

| Property | Value | Notes |
| :--- | :--- | :--- |
| **Cookie Name** | `session_token` | Configured via `SESSION_COOKIE_NAME` |
| **HttpOnly** | `True` | Inaccessible to frontend JavaScript (`document.cookie`), mitigating XSS attacks |
| **Secure** | `True` (Production) / `False` (Dev) | Automatic based on `APP_ENV` |
| **SameSite** | `Lax` | Protects against CSRF during cross-site requests |
| **Path** | `/` | Valid for all application routes |
| **Max-Age** | `86400` seconds (24 hours) | Configured via `SESSION_MAX_AGE_SECONDS` |

### Frontend Request Requirements

Because authentication uses HttpOnly cookies:
- **`fetch()`**: Always pass `{ credentials: "include" }`.
- **`axios`**: Set `axios.defaults.withCredentials = true` or `{ withCredentials: true }`.
- **Never attempt to store session tokens in `localStorage` or `sessionStorage`**.

### Standard Headers

For all JSON requests:
```http
Accept: application/json
Content-Type: application/json
```

For multipart video uploads:
```http
Accept: application/json
Content-Type: multipart/form-data
```

### Common Error Format

Standard errors return a JSON object with a human-readable `detail` field:
```json
{
  "detail": "Error description message"
}
```

Validation errors (`422 Unprocessable Entity`) return Pydantic field-level errors:
```json
{
  "detail": [
    {
      "loc": ["body", "exercise"],
      "msg": "Input should be 'squat', 'pushup' or 'lunge'",
      "type": "enum"
    }
  ]
}
```

---

# 1. Authentication APIs

Endpoints located under `/api/v1/auth`.

---

### 1.1 Initiate Google OAuth Login

- **Method**: `GET`
- **Endpoint**: `/api/v1/auth/google/login`
- **Purpose**: Initiates the Authorization Code flow with PKCE by redirecting the user's browser to the Google OAuth consent screen.
- **Authentication**: None.
- **Request**: Standard browser navigation.
- **Response**: `302 Found` redirect to Google Accounts with PKCE challenge and state parameter.
  - Sets temporary cookie: `oauth_state=<signed_token>; HttpOnly; SameSite=Lax; Max-Age=600; Path=/`

#### Request Example
```http
GET /api/v1/auth/google/login HTTP/1.1
Host: localhost:8000
```

#### Success Response
- **Status**: `302 Found`
- **Location**: `https://accounts.google.com/o/oauth2/v2/auth?client_id=...&redirect_uri=...&response_type=code&scope=openid+email+profile&state=...&code_challenge=...&code_challenge_method=S256`

#### Error Responses
- **`503 Service Unavailable`**: Google OAuth client credentials not configured on the server.
  ```json
  {
    "detail": "Google OAuth is not configured on this server."
  }
  ```

---

### 1.2 Google OAuth Callback Handler

- **Method**: `GET`
- **Endpoint**: `/api/v1/auth/google/callback`
- **Purpose**: Google redirects the browser back to this URL upon consent. The backend verifies PKCE state, exchanges the authorization code for tokens, retrieves user profile info, creates/updates the `User` in PostgreSQL, issues the `session_token` cookie, and redirects the user to the frontend application (`FRONTEND_URL`).
- **Authentication**: Requires `oauth_state` cookie set in step 1.1.
- **Query Parameters**:
  - `code` (string, required): Authorization code issued by Google.
  - `state` (string, required): Anti-CSRF state token.
  - `error` (string, optional): Error code if authorization was denied.

#### Request Example
```http
GET /api/v1/auth/google/callback?code=4/0AY0e-g...&state=xyz123 HTTP/1.1
Host: localhost:8000
Cookie: oauth_state=eyJhbGci...
```

#### Success Response
- **Status**: `302 Found`
- **Location**: `http://localhost:3000` (value of `FRONTEND_URL`)
- **Headers**:
  - `Set-Cookie: session_token=<signed_session_token>; HttpOnly; Path=/; Max-Age=86400; SameSite=Lax`
  - `Set-Cookie: oauth_state=; Max-Age=0; Path=/` (cleared)

#### Error Responses
- **`400 Bad Request`**:
  - `{"detail": "OAuth authorization failed: access_denied"}`
  - `{"detail": "Missing authorization code or state parameter"}`
  - `{"detail": "Missing or expired OAuth state cookie"}`
  - `{"detail": "Invalid OAuth state parameter"}`
  - `{"detail": "Failed to exchange authorization code with OAuth provider"}`
- **`502 Bad Gateway`**:
  - `{"detail": "Unable to contact OAuth provider"}`
  - `{"detail": "Unable to fetch user profile from OAuth provider"}`

---

### 1.3 Get Current Authenticated User

- **Method**: `GET`
- **Endpoint**: `/api/v1/auth/me`
- **Purpose**: Returns the profile of the user associated with the current session cookie.
- **Authentication**: Required (`session_token` cookie).
- **Request Headers**: `Accept: application/json`

#### Request Example
```http
GET /api/v1/auth/me HTTP/1.1
Host: localhost:8000
Cookie: session_token=...
```

#### Success Response (`200 OK`)
```json
{
  "id": "e7791a42-2a17-4be0-979e-f0fed4c60988",
  "email": "alex.athlete@example.com",
  "name": "Alex Athlete",
  "created_at": "2026-09-30T04:15:00.000000Z"
}
```

#### Error Responses
- **`401 Unauthorized`**:
  ```json
  {
    "detail": "Not authenticated"
  }
  ```

---

### 1.4 Logout Session

- **Method**: `POST`
- **Endpoint**: `/api/v1/auth/logout`
- **Purpose**: Invalidates the active session by deleting the HttpOnly session cookie.
- **Authentication**: Optional.

#### Request Example
```http
POST /api/v1/auth/logout HTTP/1.1
Host: localhost:8000
Cookie: session_token=...
```

#### Success Response (`200 OK`)
- **Headers**: `Set-Cookie: session_token=; Max-Age=0; Path=/; HttpOnly; SameSite=Lax`
```json
{
  "message": "Successfully logged out"
}
```

---

# 2. Health API

Endpoint located under `/api/v1`.

---

### 2.1 Application Health Check

- **Method**: `GET`
- **Endpoint**: `/api/v1/health`
- **Purpose**: Liveness and readiness monitoring check.
- **Authentication**: None.

#### Request Example
```http
GET /api/v1/health HTTP/1.1
Host: localhost:8000
```

#### Success Response (`200 OK`)
```json
{
  "status": "ok"
}
```

---

# 3. Job Management APIs

Endpoints located under `/api/v1/jobs`.

---

### 3.1 Create Job

- **Method**: `POST`
- **Endpoint**: `/api/v1/jobs`
- **Purpose**: Registers a new workout analysis job in `queued` status for the authenticated user.
- **Authentication**: Required (`session_token` cookie).
- **Request Headers**: `Content-Type: application/json`

#### Request Schema (`JobCreate`)

| Field | Type | Required | Allowed Values | Description |
| :--- | :--- | :--- | :--- | :--- |
| `exercise` | string | **Yes** | `"squat"`, `"pushup"`, `"lunge"` | Target exercise to analyze |
| `source_type` | string | **Yes** | `"upload"`, `"youtube"` | Submission method |
| `source_url` | string | Conditional | Valid URL string (max 2048 chars) | **Required** when `source_type="youtube"`; **must be omitted/null** when `source_type="upload"` |

#### Request Example — Direct Video Upload Job
```json
{
  "exercise": "squat",
  "source_type": "upload"
}
```

#### Request Example — YouTube Video Job
```json
{
  "exercise": "squat",
  "source_type": "youtube",
  "source_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
}
```

#### Success Response (`201 Created`)
```json
{
  "job_id": "8b3f1248-cb58-48b2-a42e-13cb09f9843a",
  "status": "queued",
  "exercise": "squat",
  "source_type": "upload",
  "source_url": null,
  "progress": 0,
  "attempts": 0,
  "error_message": null,
  "created_at": "2026-09-30T04:20:00.000000Z",
  "started_at": null,
  "completed_at": null,
  "processed_video_path": null
}
```

#### Error Responses
- **`400 Bad Request`**:
  - `{"detail": "source_url is required when source_type is 'youtube'"}`
  - `{"detail": "source_url must not be provided when source_type is 'upload'"}`
- **`401 Unauthorized`**:
  - `{"detail": "Not authenticated"}`
- **`422 Unprocessable Entity`**: Invalid exercise name or missing required fields.

---

### 3.2 List Jobs

- **Method**: `GET`
- **Endpoint**: `/api/v1/jobs`
- **Purpose**: Returns a paginated list of workout analysis jobs owned by the current user, ordered newest first (`created_at DESC`).
- **Authentication**: Required (`session_token` cookie).
- **Query Parameters**:
  - `limit` (integer, optional, default: `20`, min: `1`, max: `100`): Maximum jobs to return.
  - `offset` (integer, optional, default: `0`, min: `0`): Pagination offset.

#### Request Example
```http
GET /api/v1/jobs?limit=10&offset=0 HTTP/1.1
Host: localhost:8000
Cookie: session_token=...
```

#### Success Response (`200 OK`)
```json
{
  "items": [
    {
      "job_id": "8b3f1248-cb58-48b2-a42e-13cb09f9843a",
      "status": "completed",
      "exercise": "squat",
      "source_type": "upload",
      "source_url": null,
      "progress": 100,
      "attempts": 1,
      "error_message": null,
      "created_at": "2026-09-30T04:20:00.000000Z",
      "started_at": "2026-09-30T04:20:02.000000Z",
      "completed_at": "2026-09-30T04:20:18.000000Z",
      "processed_video_path": "processed/8b3f1248-cb58-48b2-a42e-13cb09f9843a/processed.mp4"
    }
  ],
  "total": 1,
  "limit": 10,
  "offset": 0
}
```

#### Error Responses
- **`401 Unauthorized`**: `{"detail": "Not authenticated"}`
- **`422 Unprocessable Entity`**: Invalid `limit` or `offset` query parameters.

---

### 3.3 Get Job Details

- **Method**: `GET`
- **Endpoint**: `/api/v1/jobs/{job_id}`
- **Purpose**: Retrieves current processing status, progress percentage, timestamps, and error messages for a specific job.
- **Authentication**: Required (`session_token` cookie).
- **Authorization**: Strict ownership isolation. Returns `404 Not Found` if the job belongs to another user (preventing ID enumeration).
- **Path Parameters**:
  - `job_id` (UUID, required): The unique identifier of the job.

#### Job Status Lifecycle Values

| Status | Progress | Meaning | Frontend Action |
| :--- | :--- | :--- | :--- |
| `"queued"` | `0` | Waiting in PostgreSQL queue for an available background worker | Continue polling (e.g., every 2s) |
| `"processing"` | `1–99` | Worker is actively sampling frames, extracting MediaPipe landmarks, and counting reps | Update progress bar; continue polling |
| `"completed"` | `100` | Reps analyzed, report saved, and annotated video generated | Stop polling; fetch reps, report, and video |
| `"failed"` | `0–99` | Error occurred during download, validation, or processing | Stop polling; display `error_message` |

#### Request Example
```http
GET /api/v1/jobs/8b3f1248-cb58-48b2-a42e-13cb09f9843a HTTP/1.1
Host: localhost:8000
Cookie: session_token=...
```

#### Success Response (`200 OK`)
```json
{
  "job_id": "8b3f1248-cb58-48b2-a42e-13cb09f9843a",
  "status": "processing",
  "exercise": "squat",
  "source_type": "upload",
  "source_url": null,
  "progress": 65,
  "attempts": 1,
  "error_message": null,
  "created_at": "2026-09-30T04:20:00.000000Z",
  "started_at": "2026-09-30T04:20:02.000000Z",
  "completed_at": null,
  "processed_video_path": null
}
```

#### Error Responses
- **`401 Unauthorized`**: `{"detail": "Not authenticated"}`
- **`404 Not Found`**: `{"detail": "Job not found"}` (job does not exist or belongs to another user)
- **`422 Unprocessable Entity`**: Invalid UUID syntax.

---

# 4. Video Upload & Storage

Direct video uploads for jobs created with `source_type="upload"`.

---

### 4.1 Upload Workout Video File

- **Method**: `POST`
- **Endpoint**: `/api/v1/jobs/{job_id}/video` (or storage ingestion pipeline)
- **Purpose**: Uploads an athlete's recorded workout video to permanent storage and queues it for worker processing.
- **Authentication**: Required (`session_token` cookie).
- **Content-Type**: `multipart/form-data`
- **Form Field**: `file` (binary video file)

#### Validation Constraints (`app/services/video.py`)

| Constraint | Limit | Description |
| :--- | :--- | :--- |
| **Allowed Formats** | `.mp4`, `.webm`, `.avi` | Verified via file magic bytes (`ftyp`/`moov`, WebM EBML, RIFF AVI) |
| **Maximum File Size** | `100 MB` | Configured via `MAX_VIDEO_SIZE_MB` |
| **Maximum Duration** | `60 seconds` | Probed accurately via `ffprobe` |
| **Minimum File Size** | `> 0 bytes` | Rejects empty files |

#### Request Example
```http
POST /api/v1/jobs/8b3f1248-cb58-48b2-a42e-13cb09f9843a/video HTTP/1.1
Host: localhost:8000
Content-Type: multipart/form-data; boundary=----WebKitFormBoundaryXYZ
Cookie: session_token=...

------WebKitFormBoundaryXYZ
Content-Disposition: form-data; name="file"; filename="squat_workout.mp4"
Content-Type: video/mp4

<binary video content>
------WebKitFormBoundaryXYZ--
```

#### Success Response (`200 OK`)
```json
{
  "job_id": "8b3f1248-cb58-48b2-a42e-13cb09f9843a",
  "status": "queued"
}
```

#### Error Responses
- **`400 Bad Request`**:
  - `{"detail": "Job is not configured for upload source"}`
  - `{"detail": "Video has already been uploaded for this job"}`
  - `{"detail": "File size (120.5MB) exceeds maximum limit of 100MB"}`
  - `{"detail": "Video duration (75.2s) exceeds maximum allowed 60s"}`
  - `{"detail": "File does not have a recognized video header."}`
- **`401 Unauthorized`**: `{"detail": "Not authenticated"}`
- **`404 Not Found`**: `{"detail": "Job not found"}`

---

# 5. YouTube Video Ingestion API

Endpoint located under `/api/v1/jobs`.

---

### 5.1 Ingest YouTube Video

- **Method**: `POST`
- **Endpoint**: `/api/v1/jobs/{job_id}/youtube`
- **Purpose**: Initiates server-side download and validation of the YouTube video specified in `job.source_url` during job creation.
- **Authentication**: Required (`session_token` cookie).
- **Authorization**: Job ownership required.
- **Request Body**: None (retrieves `source_url` directly from the database record).

#### Server-Side Security & SSRF Protection (`app/services/youtube.py`)
- **Domain Whitelisting**: Strictly restricts downloads to `youtube.com`, `www.youtube.com`, `m.youtube.com`, and `youtu.be`.
- **IP Inspection**: Resolves DNS and blocks loopback (`127.0.0.0/8`, `::1`), RFC1918 private subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), link-local metadata (`169.254.169.254`), and internal hostnames.
- **Duration Pre-Check**: Probes metadata before streaming; halts download immediately if duration > 60s.
- **Download Timeout**: Hard 120-second timeout prevents worker hangs.

> **Important Frontend Notice on YouTube Downloads**:
> YouTube actively detects and blocks automated downloads originating from cloud/datacenter IP ranges (e.g. AWS, GCP, Azure, DigitalOcean) with bot challenges or sign-in blocks. When blocked by YouTube, the API returns HTTP 400. In this case, the frontend should advise the user to download the video locally and submit using the direct upload option.

#### Request Example
```http
POST /api/v1/jobs/8b3f1248-cb58-48b2-a42e-13cb09f9843a/youtube HTTP/1.1
Host: localhost:8000
Cookie: session_token=...
```

#### Success Response (`200 OK`)
```json
{
  "job_id": "8b3f1248-cb58-48b2-a42e-13cb09f9843a",
  "status": "queued"
}
```

#### Error Responses
- **`400 Bad Request`**:
  - `{"detail": "Job is not configured for YouTube source"}`
  - `{"detail": "Video has already been ingested for this job"}`
  - `{"detail": "Job is missing YouTube source URL"}`
  - `{"detail": "Video duration (75s) exceeds maximum allowed 60s"}`
  - `{"detail": "SSRF protection blocked target: ..."}`
  - `{"detail": "YouTube download blocked or failed: ..."}`
- **`401 Unauthorized`**: `{"detail": "Not authenticated"}`
- **`404 Not Found`**: `{"detail": "Job not found"}`

---

# 6. Workout Results APIs

Endpoints located under `/api/v1/jobs`. Available after a job transitions to `"completed"`.

---

### 6.1 Get Repetitions Analysis

- **Method**: `GET`
- **Endpoint**: `/api/v1/jobs/{job_id}/reps`
- **Purpose**: Retrieves the detailed biomechanical metrics, timestamps, Range of Motion (ROM), tempo, form score, and specific form issues for every repetition detected.
- **Authentication**: Required (`session_token` cookie).
- **Authorization**: Job ownership required (returns 404 for other users).

#### Response Schema (`JobRepsResponse`)

| Field | Type | Description |
| :--- | :--- | :--- |
| `job_id` | UUID | Identifier of the workout job |
| `total_reps` | integer | Total completed repetitions |
| `reps` | array | List of repetition objects (`RepItemResponse`) |
| `reps[].rep_number` | integer | 1-indexed sequential repetition number |
| `reps[].start_time` | float | Repetition start timestamp in video seconds (rounded to 2 decimals) |
| `reps[].end_time` | float | Repetition end timestamp in video seconds (rounded to 2 decimals) |
| `reps[].rom` | float / null | Range of motion in degrees (`max_angle - min_angle`, rounded to 1 decimal) |
| `reps[].tempo` | float / null | Repetition duration in seconds (`end_time - start_time`, rounded to 2 decimals) |
| `reps[].form_score` | float / null | Form score from 0.0 to 100.0 (100 minus issue penalties) |
| `reps[].issues` | array | List of detected form issues (`FormIssueResponse`) |
| `reps[].issues[].code` | string | Standard issue code (e.g., `INSUFFICIENT_DEPTH`, `KNEE_ASYMMETRY`) |
| `reps[].issues[].message` | string | Human-readable explanation with exact measured angles |
| `reps[].issues[].severity` | string | Issue severity (`"warning"` or `"major"`) |

#### Request Example
```http
GET /api/v1/jobs/8b3f1248-cb58-48b2-a42e-13cb09f9843a/reps HTTP/1.1
Host: localhost:8000
Cookie: session_token=...
```

#### Success Response (`200 OK`)
```json
{
  "job_id": "8b3f1248-cb58-48b2-a42e-13cb09f9843a",
  "total_reps": 3,
  "reps": [
    {
      "rep_number": 1,
      "start_time": 1.25,
      "end_time": 2.80,
      "rom": 76.5,
      "tempo": 1.55,
      "form_score": 90.0,
      "issues": [
        {
          "code": "INSUFFICIENT_DEPTH",
          "message": "Squat depth was insufficient (knee angle 104.2° did not reach 100°)",
          "severity": "warning"
        }
      ]
    },
    {
      "rep_number": 2,
      "start_time": 3.10,
      "end_time": 4.65,
      "rom": 82.0,
      "tempo": 1.55,
      "form_score": 100.0,
      "issues": []
    },
    {
      "rep_number": 3,
      "start_time": 5.00,
      "end_time": 6.70,
      "rom": 78.0,
      "tempo": 1.70,
      "form_score": 80.0,
      "issues": [
        {
          "code": "KNEE_ASYMMETRY",
          "message": "Significant knee asymmetry detected (18.5° difference exceeds 15°)",
          "severity": "warning"
        },
        {
          "code": "INSUFFICIENT_DEPTH",
          "message": "Squat depth was insufficient (knee angle 102.1° did not reach 100°)",
          "severity": "warning"
        }
      ]
    }
  ]
}
```

#### Error Responses
- **`401 Unauthorized`**: `{"detail": "Not authenticated"}`
- **`404 Not Found`**: `{"detail": "Job not found"}`

---

### 6.2 Get Workout Summary Report

- **Method**: `GET`
- **Endpoint**: `/api/v1/jobs/{job_id}/report`
- **Purpose**: Retrieves high-level workout session summary metrics (total reps, average ROM, average tempo, average form score, and deterministic coaching summary).
- **Authentication**: Required (`session_token` cookie).
- **Authorization**: Job ownership required.

#### Response Schema (`JobReportResponse`)

| Field | Type | Description |
| :--- | :--- | :--- |
| `job_id` | UUID | Identifier of the workout job |
| `total_reps` | integer | Total completed repetitions |
| `average_rom` | float / null | Average Range of Motion across reps in degrees (null if unavailable) |
| `average_tempo` | float / null | Average repetition tempo in seconds (null if unavailable) |
| `average_score` | float / null | Average form quality score from 0.0 to 100.0 |
| `summary` | string / null | Concise, deterministic summary string (e.g. `"Completed 3 squat reps with an average form score of 90.0."`) |

#### Request Example
```http
GET /api/v1/jobs/8b3f1248-cb58-48b2-a42e-13cb09f9843a/report HTTP/1.1
Host: localhost:8000
Cookie: session_token=...
```

#### Success Response (`200 OK`)
```json
{
  "job_id": "8b3f1248-cb58-48b2-a42e-13cb09f9843a",
  "total_reps": 3,
  "average_rom": 78.8,
  "average_tempo": 1.60,
  "average_score": 90.0,
  "summary": "Completed 3 squat reps with an average form score of 90.0."
}
```

#### Error Responses
- **`401 Unauthorized`**: `{"detail": "Not authenticated"}`
- **`404 Not Found`**:
  - `{"detail": "Job not found"}` (job does not exist or owned by another user)
  - `{"detail": "Report not found for this job"}` (job has not yet completed processing)

---

### 6.3 Stream Processed Workout Video

- **Method**: `GET`
- **Endpoint**: `/api/v1/jobs/{job_id}/video`
- **Purpose**: Streams the processed MP4 video containing:
  - **Pose Skeleton Overlay**: All 33 MediaPipe body joints and connections drawn in real-time.
  - **Rep Counter HUD**: Prominent real-time rep counter badge (`REPS: <count>`) and exercise name.
- **Authentication**: Required (`session_token` cookie).
- **Authorization**: Job ownership required.
- **Path Traversal Protection**: Strictly restricts paths to within the server's storage root (`MEDIA_ROOT`).
- **Response Format**: `video/mp4` binary stream (compatible with standard browser `<video>` tags and range requests).

#### Request Example
```http
GET /api/v1/jobs/8b3f1248-cb58-48b2-a42e-13cb09f9843a/video HTTP/1.1
Host: localhost:8000
Cookie: session_token=...
```

#### Success Response (`200 OK`)
- **Headers**:
  - `Content-Type: video/mp4`
  - `Content-Disposition: inline; filename="processed_8b3f1248-cb58-48b2-a42e-13cb09f9843a.mp4"`
  - `Accept-Ranges: bytes`
- **Body**: Binary MP4 video stream.

#### Frontend HTML5 Video Usage Example
```html
<video controls width="640" height="480">
  <source src="http://localhost:8000/api/v1/jobs/8b3f1248-cb58-48b2-a42e-13cb09f9843a/video" type="video/mp4">
  Your browser does not support the video tag.
</video>
```
*Note: In authenticated frontend applications, fetch the video with credentials (e.g. creating a Blob URL via `URL.createObjectURL(blob)`) or ensure cookies are transmitted on the media request.*

#### Error Responses
- **`401 Unauthorized`**: `{"detail": "Not authenticated"}`
- **`404 Not Found`**:
  - `{"detail": "Job not found"}` (job does not exist or belongs to another user)
  - `{"detail": "Processed video not available for this job"}` (job is still processing or failed)
  - `{"detail": "Processed video file not found on storage"}`

---

# 7. Quick Reference API Table

| Method | Endpoint | Auth | Request Body | Response Content | Description |
| :--- | :--- | :---: | :--- | :--- | :--- |
| `GET` | `/` | No | — | `{"message": "..."}` | Root welcome endpoint |
| `GET` | `/api/v1/health` | No | — | `{"status": "ok"}` | Application liveness probe |
| `GET` | `/api/v1/auth/google/login` | No | — | `302 Redirect` | Start Google OAuth login |
| `GET` | `/api/v1/auth/google/callback` | State Cookie | — | `302 Redirect` | Google OAuth callback handler |
| `GET` | `/api/v1/auth/me` | **Yes** | — | `UserResponse` JSON | Current authenticated user profile |
| `POST` | `/api/v1/auth/logout` | Optional | — | `{"message": "..."}` | Clear session cookie |
| `POST` | `/api/v1/jobs` | **Yes** | `JobCreate` JSON | `JobResponse` JSON | Create new workout analysis job |
| `GET` | `/api/v1/jobs` | **Yes** | — (query params) | `JobListResponse` JSON | List user jobs (paginated) |
| `GET` | `/api/v1/jobs/{job_id}` | **Yes** | — | `JobResponse` JSON | Get status and progress of job |
| `POST` | `/api/v1/jobs/{job_id}/video` | **Yes** | `multipart/form-data` | `{"job_id": "...", "status": "queued"}` | Upload video file for job |
| `POST` | `/api/v1/jobs/{job_id}/youtube`| **Yes** | — | `JobIngestResponse` JSON | Trigger YouTube video ingestion |
| `GET` | `/api/v1/jobs/{job_id}/reps` | **Yes** | — | `JobRepsResponse` JSON | Get completed reps and form issues |
| `GET` | `/api/v1/jobs/{job_id}/report` | **Yes** | — | `JobReportResponse` JSON | Get aggregate workout report |
| `GET` | `/api/v1/jobs/{job_id}/video` | **Yes** | — | `video/mp4` binary stream | Stream annotated workout video |

---

# 8. Recommended Frontend Integration Flows

### Flow A: Direct Video Upload

```text
1. User Logs In
   └── Browser visits: GET /api/v1/auth/google/login
   └── Completes Google OAuth consent
   └── Browser redirects to frontend with session_token cookie

2. Create Job
   └── POST /api/v1/jobs
       Body: { "exercise": "squat", "source_type": "upload" }
       Receives: { "job_id": "<ID>", "status": "queued" }

3. Upload Video File
   └── POST /api/v1/jobs/<ID>/video
       Form: file=<FileObject>
       Receives: { "job_id": "<ID>", "status": "queued" }

4. Poll Job Progress
   └── Loop every 2 seconds: GET /api/v1/jobs/<ID>
       Status "queued"     -> Show "In Queue..."
       Status "processing" -> Update progress bar (<progress>%)
       Status "failed"     -> Stop polling; show error_message
       Status "completed"  -> Stop polling; proceed to results!

5. Fetch Results & Render UI
   ├── GET /api/v1/jobs/<ID>/report -> Display total reps, avg score, avg ROM, coaching summary
   ├── GET /api/v1/jobs/<ID>/reps   -> Render repetition timeline, ROM charts, and form issues
   └── GET /api/v1/jobs/<ID>/video  -> Display annotated processed video in <video> player
```

---

### Flow B: YouTube Submission

```text
1. User Logs In
   └── Authenticates via Google OAuth

2. Create Job with YouTube URL
   └── POST /api/v1/jobs
       Body: {
         "exercise": "pushup",
         "source_type": "youtube",
         "source_url": "https://www.youtube.com/watch?v=..."
       }
       Receives: { "job_id": "<ID>", "status": "queued" }

3. Trigger Ingestion
   └── POST /api/v1/jobs/<ID>/youtube
       Backend downloads video server-side and enforces SSRF checks.
       Receives: { "job_id": "<ID>", "status": "queued" }
       (If blocked by YouTube, prompt user to use direct upload option)

4. Poll Job Progress
   └── Loop every 2 seconds: GET /api/v1/jobs/<ID>
       Wait for status: "completed"

5. Fetch Results & Render UI
   ├── GET /api/v1/jobs/<ID>/report
   ├── GET /api/v1/jobs/<ID>/reps
   └── GET /api/v1/jobs/<ID>/video
```

---

# 9. Frontend Authentication Best Practices

### Fetch Example (Native JavaScript)

```javascript
// Example helper for authenticated API calls
async function apiRequest(endpoint, options = {}) {
  const response = await fetch(`http://localhost:8000/api/v1${endpoint}`, {
    ...options,
    credentials: "include", // CRITICAL: Transmits session_token cookie
    headers: {
      "Accept": "application/json",
      ...(options.headers || {}),
    },
  });

  if (response.status === 401) {
    // Session expired or unauthenticated: redirect to login
    window.location.href = "http://localhost:8000/api/v1/auth/google/login";
    return null;
  }

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(errorData.detail || "Request failed");
  }

  return response.json();
}
```

### Video Stream Fetch Example (Protected Media Player)

To render the protected processed video inside a React/Vue/vanilla player while transmitting authentication cookies:

```javascript
async function loadProcessedVideo(jobId) {
  const response = await fetch(`http://localhost:8000/api/v1/jobs/${jobId}/video`, {
    credentials: "include",
  });

  if (!response.ok) {
    throw new Error("Video not available yet");
  }

  const videoBlob = await response.blob();
  const videoObjectUrl = URL.createObjectURL(videoBlob);
  document.getElementById("workout-player").src = videoObjectUrl;
}
```

---

# 10. HTTP Status Codes & Error Handling Matrix

The backend consistently adheres to standard HTTP status codes:

| Status Code | Reason | Cause / Context | Recommended Frontend Action |
| :---: | :--- | :--- | :--- |
| **`200`** | `OK` | Successful GET/POST operation | Render returned data |
| **`201`** | `Created` | Job successfully created | Store `job_id` and proceed to upload/ingest |
| **`302`** | `Found` | OAuth redirects | Let browser follow redirection |
| **`400`** | `Bad Request` | Validation failure (e.g. video > 60s, wrong source type, invalid YouTube URL) | Display `error.detail` in a user banner or toast |
| **`401`** | `Unauthorized` | Missing or invalid `session_token` cookie | Redirect user to Google OAuth login |
| **`404`** | `Not Found` | Job does not exist, belongs to another user, or report/video is not yet generated | Show "Not Found" or "Still processing" |
| **`422`** | `Unprocessable Entity` | Schema validation error (invalid enum or missing JSON parameter) | Validate input fields before submission |
| **`500`** | `Internal Server Error` | Unexpected backend server error | Display friendly "Something went wrong" message |
| **`502`** | `Bad Gateway` | Google OAuth token/userinfo endpoint could not be reached | Advise user to retry login |
| **`503`** | `Service Unavailable` | Google OAuth credentials not set in server `.env` | Notify system administrator |
