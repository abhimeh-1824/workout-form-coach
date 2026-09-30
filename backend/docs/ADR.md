# Architecture Decision Records (ADR)

## ADR 001: Server-Side YouTube Video Ingestion & SSRF Protection

### Status
Accepted

### Context
Users can submit workout videos for form analysis either by directly uploading an MP4 video or by supplying a YouTube URL (`https://www.youtube.com/watch?v=...` or `https://youtu.be/...`). The backend server is tasked with securely fetching the YouTube video server-side before queuing it for processing.

### Decision
1. **Server-Side Download Pipeline**: We support server-side YouTube video ingestion via `yt-dlp` invoked from the dedicated endpoint `POST /api/v1/jobs/{job_id}/youtube`.
2. **Metadata Duration Pre-Check**: Before downloading video streams, the system probes video metadata. If reported duration exceeds 60 seconds, download is halted immediately.
3. **Multi-Stage Validation**: After download to temporary isolated storage, the actual video file is strictly validated for container format, size (<= 100MB), and true duration (<= 60s) before moving to permanent job storage.

### Security & SSRF Protection
- **Strict Domain Whitelisting**: Only official YouTube domains (`www.youtube.com`, `youtube.com`, `m.youtube.com`, `youtu.be`) are accepted; arbitrary or user-controlled hostnames/IPs are rejected.
- **DNS Resolution & IP Inspection**: The system resolves all hostnames to their underlying IPv4 and IPv6 addresses and rejects loopback (`127.0.0.0/8`, `::1`), private RFC1918 subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), link-local/cloud metadata (`169.254.0.0/16`), and internal hostnames (`localhost`, `*.local`, `*.internal`).
- **Deep Redirect Validation**: Downloader redirect handling is intercepted so that every redirect hop is verified against SSRF rules and Google/YouTube video CDN boundaries (`*.googlevideo.com`).
- **Resource Constraints**: Hard download timeout (120 seconds) and file size caps (100MB) prevent denial-of-service and disk exhaustion.

### Limitations
Automated server-side YouTube downloads may occasionally be throttled or blocked by YouTube (e.g., bot detection, sign-in requirements, or cloud/datacenter IP blocking).

### Fallback
When automated server-side YouTube retrieval fails or is blocked, the API returns a structured error instructing the user to download the video locally and use the direct video upload option (`source_type: "upload"`).

## ADR 002: MediaPipe Pose for 33 Landmark Keypoint Extraction

### Status
Accepted

### Context
Workout form analysis requires extracting body joint coordinates across sequential video frames (for squats, push-ups, and lunges). The system must run on standard server hardware without mandatory GPU acceleration or heavyweight deep learning runtimes (e.g., PyTorch, TensorFlow, OpenPose, YOLO).

### Decision
1. **Model Selection**: We adopted Google MediaPipe Pose via `mediapipe.tasks.python.vision.PoseLandmarker` backed by the lightweight `pose_landmarker_lite.task` model with CPU XNNPACK execution.
2. **All 33 Landmarks**: We extract and retain all 33 standardized body landmarks (including nose, shoulders, elbows, wrists, hips, knees, ankles, heels, and foot indices) with normalized coordinates ($x, y$), relative depth ($z$), and visibility confidence.
3. **Sequential Video Mode**: Uses `RunningMode.VIDEO` with monotonic timestamps so temporal tracking can optimize inference across frames.
4. **Single-Person Assumption**: Configured with `num_poses = 1` matching workout videos focused on an individual athlete.
5. **Decoupled Architecture**: Pose estimation logic is encapsulated in `app/services/pose_detector.py`, strictly isolated from queue handling, database sessions, and workout rep logic.

### Trade-offs & Limitations
- **Single Subject Focus**: If multiple individuals are visible, MediaPipe focuses on the most prominent subject.
- **Occlusion & Missing Poses**: Frames without a detectable person return `pose_detected = False` with an empty landmark list rather than aborting the job. Videos with zero detected poses fail with clear feedback (`"No person detected in the video."`).
- **Separation of Concerns**: The pose layer outputs raw normalized landmark geometry only; joint angles, smoothing, rep counting, and form scoring belong to subsequent processing stages.
