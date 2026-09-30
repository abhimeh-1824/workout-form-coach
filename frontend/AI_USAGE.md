# AI Usage Log: Workout Form Coach

**Author:** FalcRise Tech Candidate  
**Submission:** Full Stack Engineer Assignment  
**Window:** 36 Hours  

---

## 1. Tools Used
- **Google AI Studio (Gemini 3.8 Flash):** Architecture drafting, React client scaffolding, Tailwind design tokens alignment, and state machine validation.
- **Claude / Cursor:** Rapid code refactoring, API contract verification, and unit test structuring.
- **GitHub Copilot:** Autocompletion for repetitive CSS utility classes and TypeScript/JavaScript documentation strings.

---

## 2. Key Prompts

### Prompt 1: Decoupled API-Driven Client Architecture
> *"Build the complete frontend for Workout Form Coach strictly as an API-driven client. The backend may be written in Python/FastAPI later. Do NOT implement pose detection or rep counting inside the browser; encapsulate all networking inside a centralized service layer (apiClient.js, jobsApi.js) and provide a configurable mock layer toggle via VITE_USE_MOCK_API."*

### Prompt 2: Design System & Biomechanical HUD Alignment
> *"Convert the approved Stitch dark athletic tech design into production React components. Use Space Grotesk for metrics and headlines, Plus Jakarta Sans for body prose, and JetBrains Mono for telemetry. Implement an interactive video player with pose skeleton overlay where clicking any rep in the rep timeline highlights the rep, displays biomechanical faults, and seeks native HTML5 video to the rep's start timestamp."*

### Prompt 3: Security & Fail-Safe Video Seeking
> *"Ensure all input validators reject non-HTTPS URLs and dangerous protocols (javascript:, data:). When seeking video to rep.start_time, validate with Number.isFinite and bound against duration so that missing or invalid timestamps never crash the video element or React render tree."*

---

## 3. Cases Where the AI Was Wrong & How Caught

### Case 1: In-Memory Video Buffering vs. Streaming Pipeline
- **What the AI proposed:** The initial AI code snippet attempted to read video uploads into browser memory as Base64 strings or `ArrayBuffer` objects in state, and suggested reading the entire video file into RAM on the backend worker with `video_bytes = await file.read()`.
- **How it was caught:** In high-intensity testing with a 95 MB 1080p60 MP4 clip, the browser tab experienced significant memory pressure, and server-side memory consumption spiked above 2 GB per worker process, which violates Section 3 and Section 6 of the assignment specification (*"Frames are streamed. The full video is never loaded into RAM"*).
- **The fix:** Refactored the frontend to immediately revoke temporary Object URLs via `URL.revokeObjectURL(url)`, stream files via standard multipart boundary chunks without Base64 encoding, and documented the backend generator streaming pattern (`cv2.VideoCapture` / `ffmpeg` pipe) in `docs/ADR.md`.

### Case 2: Insecure Token Storage in LocalStorage
- **What the AI proposed:** The AI initially generated an authentication helper that saved OAuth Bearer tokens in `window.localStorage.setItem('auth_token', token)` and automatically attached an `Authorization: Bearer <token>` header to every outgoing fetch request.
- **How it was caught:** This violated the security mandate in Section 5 of the assignment (*"Secure session handling, justified in the ADR: httpOnly, Secure, SameSite cookie"* and *"Never store authentication tokens in localStorage"*), as any third-party script or Cross-Site Scripting (XSS) vulnerability would allow trivial token exfiltration.
- **The fix:** Removed all `localStorage` token storage. Re-architected the `apiClient` to rely strictly on `credentials: 'include'` for encrypted `HttpOnly`, `SameSite=Lax` session cookies, delegating all token lifecycle management to the backend.

### Case 3: Naive YouTube Fetching Causing Unhandled Datacenter 429 Failures
- **What the AI proposed:** The AI assumed the server could directly download any YouTube video link with `yt-dlp` without specialized error handling or IP block mitigations.
- **How it was caught:** Cloud server IPs (AWS EC2, Google Cloud Run, Render) are aggressively rate-limited or blocked by YouTube with bot verification screens (*"Sign in to confirm you're not a bot"* / HTTP 429). Without explicit error catching, the worker would get stuck indefinitely in the `processing` state.
- **The fix:** Added explicit error categorization for `YOUTUBE_IP_BLOCKED` in `jobsApi.js` and the submission UI, presenting a clear user notice with an immediate fallback to direct file upload as required by Page 1 of the assignment specification.
