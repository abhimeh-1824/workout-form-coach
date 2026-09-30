from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings loaded from environment or .env file."""

    APP_NAME: str = "Workout Form Coach"
    APP_ENV: str = "development"
    FRONTEND_URL: str = "http://localhost:3000"
    API_V1_PREFIX: str = "/api/v1"
    DATABASE_URL: str

    # Google OAuth & Session Security
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"
    SESSION_SECRET: str = "workout_form_coach_dev_session_secret_change_in_production"
    SESSION_COOKIE_NAME: str = "session"
    SESSION_MAX_AGE_SECONDS: int = 604800  # 7 days

    # Media Storage and Video Constraints
    MEDIA_ROOT: str = "media"
    MAX_VIDEO_SIZE_MB: int = 100
    MAX_VIDEO_DURATION_SECONDS: int = 60
    YOUTUBE_DOWNLOAD_TIMEOUT_SECONDS: int = 120

    # Background Job Worker
    WORKER_POLL_INTERVAL_SECONDS: float = 2.0
    PROCESSING_FPS: int = 15

    # MediaPipe Pose Settings
    POSE_MODEL_PATH: str = "app/models/assets/pose_landmarker_lite.task"
    POSE_MIN_DETECTION_CONFIDENCE: float = 0.5
    POSE_MIN_TRACKING_CONFIDENCE: float = 0.5

    # Biomechanics & Smoothing Settings
    LANDMARK_SMOOTHING_ALPHA: float = 0.5
    LANDMARK_VISIBILITY_THRESHOLD: float = 0.5

    # Rep Counting Thresholds (degrees)
    SQUAT_UP_ANGLE: float = 160.0
    SQUAT_DOWN_ANGLE: float = 100.0
    PUSHUP_UP_ANGLE: float = 160.0
    PUSHUP_DOWN_ANGLE: float = 90.0
    LUNGE_UP_ANGLE: float = 160.0
    LUNGE_DOWN_ANGLE: float = 100.0

    # Workout Form Analysis Settings
    SQUAT_DEPTH_ANGLE: float = 100.0
    PUSHUP_DEPTH_ANGLE: float = 90.0
    LUNGE_DEPTH_ANGLE: float = 100.0

    KNEE_ASYMMETRY_THRESHOLD: float = 15.0
    ELBOW_ASYMMETRY_THRESHOLD: float = 15.0
    LUNGE_ASYMMETRY_THRESHOLD: float = 15.0

    FORM_WARNING_PENALTY: float = 10.0
    FORM_MAJOR_PENALTY: float = 20.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()


settings: Settings = get_settings()
