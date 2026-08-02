"""add code_scan_jobs and code_findings

Revision ID: c3f8a1d92b7e
Revises: 9a1f2b6c3d4e
Create Date: 2026-08-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c3f8a1d92b7e'
down_revision: Union[str, None] = '9a1f2b6c3d4e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'code_scan_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('upload_path', sa.String(), nullable=False),
        # create_type=False - reuses the 'scanstatus' enum type already
        # created for scan_jobs.status (see 15544c9ecca8), same values.
        sa.Column(
            'status',
            postgresql.ENUM('pending', 'running', 'completed', 'failed', name='scanstatus', create_type=False),
            nullable=False,
        ),
        sa.Column('container_id', sa.String(), nullable=True),
        sa.Column('report_path', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'code_findings',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('code_scan_job_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source', sa.String(), nullable=False),
        sa.Column('vuln_type', sa.String(), nullable=False),
        # create_type=False - reuses the 'severity' enum type already
        # created for findings.severity (see 15544c9ecca8).
        sa.Column(
            'severity',
            postgresql.ENUM('critical', 'high', 'medium', 'low', 'info', name='severity', create_type=False),
            nullable=False,
        ),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('evidence', sa.Text(), nullable=True),
        sa.Column('remediation', sa.Text(), nullable=False),
        sa.Column('affected_file', sa.String(), nullable=False),
        sa.Column('line_number', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['code_scan_job_id'], ['code_scan_jobs.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('code_findings')
    op.drop_table('code_scan_jobs')
