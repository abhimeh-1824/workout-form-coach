# Architectural Decision Record (ADR): Workout Form Coach

**Status:** Accepted  
**Project:** Workout Form Coach  
**Author:** FalcRise Tech Candidate  
**Date:** September 2026  

---

## 1. Context & Business Problem
Athletes performing movements (Squat, Push-up, Lunge) need real-time, objective biomechanical feedback to prevent joint injury (e.g., knee valgus, lumbar rounding) and ensure proper range-of-motion (ROM). The platform must ingest user video via file upload ($\le 100\text{ MB}$, $\le 60\text{s}$) or YouTube URLs, asynchronously process frames on worker nodes, track reps via a finite-state machine, and render an interactive HUD where clicking flagged reps scrubs the video to the deviation timestamp.

---

## 2. Model Selection & Biomechanical Vision Pipeline
**Decision:** Selected **MediaPipe Pose** (with ONNX runtime fallback for server workers).

### Justification:
- **Accuracy & Keypoints:** Emits 33 3D body keypoints (including critical joint axes: hips, knees, ankles, shoulders, elbows, wrists) with sub-pixel landmark coordinates and occluded visibility confidence scores.
- **Latency & Speed:** Runs at 60+ FPS on standard x86 CPU / GPU nodes without requiring costly dedicated multi-GPU clusters.
- **Cost & Licensing:** Fully open-source under the Apache 2.0 license, incurring **\$0 per-frame API cost**, unlike hosted commercial vision APIs (e.g., AWS Rekognition or GCP Video AI which charge per minute of video).
- **Privacy & Security:** Videos are processed ephemerally within secure internal worker enclaves; biometric landmarks are extracted without sending raw footage to third-party model providers.

---

## 3. Video Ingest & Frame Streaming Architecture
**Decision:** Stream frames sequentially using `ffmpeg` / `cv2.VideoCapture` generator pipelines. The full video is **never loaded into RAM**.

### Justification:
- Loading raw 1080p60 videos into RAM consumes $\sim 2\text{–}4\text{ GB}$ per concurrent worker, causing Out-Of-Memory (OOM) crashes under heavy load.
- Streaming decouples disk I/O from inference: frames are decoded on-the-fly at a configurable sampling rate (e.g., 30 FPS or 60 FPS), piped through landmark estimation, smoothed via exponential moving average (EMA), and discarded.

---

## 4. Multi-Person Handling Strategy
**Decision:** Primary Subject Selection with Strict Crowded-Frame Policy.

### Specification:
- If zero persons are detected in $\ge 30\%$ of video frames, the job fails cleanly with error code `ERR_CV_NO_PERSON_DETECTED` (*"No person in frame. Please ensure full body is visible."*).
- If multiple people are detected in the frame:
  - The model calculates bounding box area $\times$ tracking confidence.
  - The largest central athlete bounding box is isolated as the primary subject.
  - If a foreground obstruction crosses the subject (occlusion confidence drops below $40\%$), the job flags `ERR_CV_OCCLUSION_DETECTED` with specific frame intervals.

---

## 5. YouTube URL Ingestion & Datacenter IP Blocking Strategy
**Decision:** Two-tier ingest with graceful cloud IP block detection and instant file upload fallback.

### Specification:
- Cloud datacenters (AWS, GCP, DigitalOcean, Render) frequently encounter YouTube HTTP `429 Too Many Requests` or bot challenges (`Sign in to confirm you're not a bot`).
- **Mitigation:**
  1. The backend tests the URL using `yt-dlp` with strict argument arrays (`--no-playlist`, `--max-filesize 100M`, `--socket-timeout 10`).
  2. If YouTube returns a bot challenge or IP block, the API responds with `422 Unprocessable Entity` and a designated error payload:
     ```json
     {
       "error": "YOUTUBE_IP_BLOCKED",
       "message": "YouTube is currently rate-limiting cloud servers. Please download the clip and use Direct File Upload instead.",
       "fallback_action": "upload"
     }
     ```
  3. The frontend catches this code and automatically switches the submission tab to **Video File Upload** with the helpful guidance banner.

---

## 6. Authentication & Session Security (RBAC)
**Decision:** Authorization Code Flow with PKCE + `HttpOnly`, `Secure`, `SameSite=Lax` Cookie Sessions.

### Justification:
- Storing access or refresh tokens in browser `localStorage` or `sessionStorage` exposes athletes to Cross-Site Scripting (XSS) credential theft.
- By issuing an encrypted, signed session cookie (`auth_session`), tokens are inaccessible to JavaScript.
- **Tenant Authorization:** Every database query enforces `WHERE job.user_id = :current_user_id`. Attempting to query another athlete's `job_id` responds with `403 Forbidden` (*"You don't have permission to view this workout."*).

---

## 7. Database & Worker Queue (Idempotency)
**Decision:** PostgreSQL with transactional `SKIP LOCKED` worker reservation.

```sql
-- Worker atomic claim pattern
UPDATE jobs
SET status = 'processing', worker_id = :worker_id, updated_at = NOW()
WHERE id = (
  SELECT id FROM jobs
  WHERE status = 'queued'
  ORDER BY created_at ASC
  LIMIT 1
  FOR UPDATE SKIP LOCKED
)
RETURNING *;
```

### Idempotency & Crash Recovery:
- If a worker crashes mid-inference, intermediate progress frames are stored with checkpoint offsets.
- When retried via `POST /jobs/:id/retry`, existing rep rows are deleted or updated idempotently, preventing duplicate rep counts.

---

## 8. Rollback & Deployment Strategy
- **Container Registry:** Tagged Docker builds on GitHub Container Registry (`ghcr.io`).
- **Smoke Testing:** CI/CD post-deployment script queries `GET /health`. If `/health` does not return `200 OK` within 45 seconds, the release automatically rolls back to the previous stable image tag (`IMAGE_TAG_PREVIOUS`).
- **Zero-Downtime Migrations:** Database migrations only use additive schema changes (add column with null/default, create index concurrently); destructive column drops are split across two deployment releases.

---

## 9. Tradeoffs & Future Enhancements

### What was cut to respect the 10-hour effort cap:
1. **Live WebRTC Ingest:** Focused on asynchronous video upload and YouTube fetching rather than live peer-to-peer browser camera streaming, as asynchronous processing ensures reliable 60 FPS analysis regardless of user CPU constraints.
2. **Custom Neural Model Fine-tuning:** Leveraged pretrained MediaPipe 33-point topology instead of training custom PyTorch weights, saving massive GPU compute hours while ensuring zero license friction.

### What would be implemented with more time:
1. **Real-time SSE / WebSocket streaming:** Replace client-side 3s polling with Server-Sent Events (`/jobs/:id/stream`) for sub-second pipeline step feedback.
2. **3D Interactive Mesh Viewer:** Render Three.js rigged skeleton in 3D spatial space allowing 360° camera rotation around the athlete during the rep.
