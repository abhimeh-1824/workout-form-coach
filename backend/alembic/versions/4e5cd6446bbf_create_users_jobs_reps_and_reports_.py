"""create users jobs reps and reports tables

Revision ID: 4e5cd6446bbf
Revises: 7a4a7b799f66
Create Date: 2026-09-30 01:29:58.994452

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '4e5cd6446bbf'
down_revision: Union[str, Sequence[str], None] = '7a4a7b799f66'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Enum definitions for PostgreSQL
job_status_enum = sa.Enum(
    'queued',
    'processing',
    'completed',
    'failed',
    name='job_status',
)
exercise_type_enum = sa.Enum(
    'squat',
    'pushup',
    'lunge',
    name='exercise_type',
)
source_type_enum = sa.Enum(
    'upload',
    'youtube',
    name='source_type',
)


def upgrade() -> None:
    """Create users, jobs, reps, and reports tables."""
    # 1. Users table
    op.create_table(
        'users',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('provider_user_id', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'provider',
            'provider_user_id',
            name='uq_users_provider_provider_user_id',
        ),
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # 2. Jobs table
    op.create_table(
        'jobs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('status', job_status_enum, server_default='queued', nullable=False),
        sa.Column('exercise', exercise_type_enum, nullable=False),
        sa.Column('source_type', source_type_enum, nullable=False),
        sa.Column('source_url', sa.String(length=2048), nullable=True),
        sa.Column('video_path', sa.String(length=1024), nullable=True),
        sa.Column('processed_video_path', sa.String(length=1024), nullable=True),
        sa.Column('progress', sa.Integer(), server_default='0', nullable=False),
        sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            'progress >= 0 AND progress <= 100',
            name='ck_jobs_progress_range',
        ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_jobs_user_id'), 'jobs', ['user_id'], unique=False)
    # Justified Worker Index: FIFO claiming for queued jobs
    op.create_index(
        'ix_jobs_status_created_at',
        'jobs',
        ['status', 'created_at'],
        unique=False,
    )

    # 3. Reps table
    op.create_table(
        'reps',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('job_id', sa.UUID(), nullable=False),
        sa.Column('rep_number', sa.Integer(), nullable=False),
        sa.Column('start_time', sa.Float(), nullable=False),
        sa.Column('end_time', sa.Float(), nullable=False),
        sa.Column('rom', sa.Float(), nullable=True),
        sa.Column('tempo', sa.Float(), nullable=True),
        sa.Column('form_score', sa.Float(), nullable=True),
        sa.Column(
            'issues',
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite'),
            nullable=True,
        ),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            'form_score IS NULL OR (form_score >= 0 AND form_score <= 100)',
            name='ck_reps_form_score_range',
        ),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('job_id', 'rep_number', name='uq_reps_job_id_rep_number'),
    )
    op.create_index(op.f('ix_reps_job_id'), 'reps', ['job_id'], unique=False)

    # 4. Reports table
    op.create_table(
        'reports',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('job_id', sa.UUID(), nullable=False),
        sa.Column('total_reps', sa.Integer(), server_default='0', nullable=False),
        sa.Column('average_score', sa.Float(), nullable=True),
        sa.Column('average_rom', sa.Float(), nullable=True),
        sa.Column('average_tempo', sa.Float(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('job_id', name='uq_reports_job_id'),
    )


def downgrade() -> None:
    """Drop reports, reps, jobs, and users tables and associated enums."""
    op.drop_table('reports')

    op.drop_index(op.f('ix_reps_job_id'), table_name='reps')
    op.drop_table('reps')

    op.drop_index('ix_jobs_status_created_at', table_name='jobs')
    op.drop_index(op.f('ix_jobs_user_id'), table_name='jobs')
    op.drop_table('jobs')

    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')

    # Drop custom PostgreSQL enums
    bind = op.get_bind()
    source_type_enum.drop(bind, checkfirst=True)
    exercise_type_enum.drop(bind, checkfirst=True)
    job_status_enum.drop(bind, checkfirst=True)
