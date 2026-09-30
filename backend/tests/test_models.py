import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from app.db.base import (
    Base,
    ExerciseType,
    Job,
    JobStatus,
    Rep,
    Report,
    SourceType,
    User,
)


@pytest.fixture
def db_session():
    """In-memory database session fixture for model testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine)


def test_models_registered_in_metadata() -> None:
    """Verify all four tables are registered with Base.metadata."""
    table_names = list(Base.metadata.tables.keys())
    assert "users" in table_names
    assert "jobs" in table_names
    assert "reps" in table_names
    assert "reports" in table_names


def test_worker_index_exists() -> None:
    """Verify the justified worker claiming index (status, created_at) exists on jobs table."""
    jobs_table = Base.metadata.tables["jobs"]
    index_names = {idx.name for idx in jobs_table.indexes}
    assert "ix_jobs_status_created_at" in index_names


def test_unique_constraints_exist() -> None:
    """Verify required unique constraints on users, reps, and reports."""
    users_table = Base.metadata.tables["users"]
    reps_table = Base.metadata.tables["reps"]
    reports_table = Base.metadata.tables["reports"]

    # Users constraint: (provider, provider_user_id)
    user_uq_names = {uq.name for uq in users_table.constraints if hasattr(uq, "name")}
    assert "uq_users_provider_provider_user_id" in user_uq_names

    # Reps constraint: (job_id, rep_number)
    rep_uq_names = {uq.name for uq in reps_table.constraints if hasattr(uq, "name")}
    assert "uq_reps_job_id_rep_number" in rep_uq_names

    # Reports constraint: job_id unique
    report_uq_names = {uq.name for uq in reports_table.constraints if hasattr(uq, "name")}
    assert "uq_reports_job_id" in report_uq_names


def test_check_constraints_exist() -> None:
    """Verify check constraints for jobs progress and reps form_score."""
    jobs_table = Base.metadata.tables["jobs"]
    reps_table = Base.metadata.tables["reps"]

    job_ck_names = {ck.name for ck in jobs_table.constraints if hasattr(ck, "name")}
    assert "ck_jobs_progress_range" in job_ck_names

    rep_ck_names = {ck.name for ck in reps_table.constraints if hasattr(ck, "name")}
    assert "ck_reps_form_score_range" in rep_ck_names


def test_model_relationships_and_cascades(db_session: Session) -> None:
    """Verify User -> Jobs -> Reps and Job -> Report relationships."""
    user = User(
        id=uuid.uuid4(),
        provider="google",
        provider_user_id="google-sub-12345",
        email="athlete@example.com",
        name="Athlete One",
    )
    db_session.add(user)
    db_session.commit()

    job = Job(
        id=uuid.uuid4(),
        user_id=user.id,
        status=JobStatus.QUEUED,
        exercise=ExerciseType.SQUAT,
        source_type=SourceType.UPLOAD,
        video_path="uploads/squat_clip.mp4",
    )
    db_session.add(job)
    db_session.commit()

    rep = Rep(
        id=uuid.uuid4(),
        job_id=job.id,
        rep_number=1,
        start_time=0.5,
        end_time=3.2,
        rom=90.0,
        tempo=2.7,
        form_score=88.5,
        issues={"knee_valgus": False, "chest_drop": True},
    )
    report = Report(
        id=uuid.uuid4(),
        job_id=job.id,
        total_reps=1,
        average_score=88.5,
        average_rom=90.0,
        average_tempo=2.7,
        summary="Good squat depth, slight chest dip on descent.",
    )
    db_session.add_all([rep, report])
    db_session.commit()

    # Query through relationships
    fetched_user = db_session.get(User, user.id)
    assert fetched_user is not None
    assert len(fetched_user.jobs) == 1

    fetched_job = fetched_user.jobs[0]
    assert fetched_job.user.id == user.id
    assert len(fetched_job.reps) == 1
    assert fetched_job.reps[0].rep_number == 1
    assert fetched_job.report is not None
    assert fetched_job.report.summary == "Good squat depth, slight chest dip on descent."


def test_enum_values() -> None:
    """Verify enum allowed values."""
    assert [e.value for e in JobStatus] == ["queued", "processing", "completed", "failed"]
    assert [e.value for e in ExerciseType] == ["squat", "pushup", "lunge"]
    assert [e.value for e in SourceType] == ["upload", "youtube"]
