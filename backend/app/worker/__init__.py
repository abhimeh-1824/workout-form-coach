"""Background worker package for Workout Form Coach."""

__all__ = ["run_worker"]


def __getattr__(name: str):
    if name == "run_worker":
        from app.worker.worker import run_worker
        return run_worker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

