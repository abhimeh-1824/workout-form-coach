from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health", response_model=dict[str, str], summary="Health Check")
def health_check() -> dict[str, str]:
    """Health check endpoint returning application status."""
    return {"status": "ok"}
