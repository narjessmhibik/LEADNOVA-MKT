"""add scoring and email fields

Revision ID: a1b2c3d4e5f6
Revises: 7c3d4d72190b
Create Date: 2026-06-02 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '7c3d4d72190b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Colonnes scoring XGBoost + segmentation K-Means
    op.add_column('leads', sa.Column('lead_score', sa.Float(), nullable=True))
    op.add_column('leads', sa.Column('scored_at', sa.DateTime(), nullable=True))
    op.add_column('leads', sa.Column('segment', sa.String(), nullable=True))
    op.add_column('leads', sa.Column('segmented_at', sa.DateTime(), nullable=True))

    # Colonnes email generator
    op.add_column('leads', sa.Column('email_subject_a', sa.String(), nullable=True))
    op.add_column('leads', sa.Column('email_body_a', sa.Text(), nullable=True))
    op.add_column('leads', sa.Column('email_subject_b', sa.String(), nullable=True))
    op.add_column('leads', sa.Column('email_body_b', sa.Text(), nullable=True))
    op.add_column('leads', sa.Column('email_sent', sa.Boolean(), nullable=True, default=False))
    op.add_column('leads', sa.Column('email_sent_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('leads', 'lead_score')
    op.drop_column('leads', 'scored_at')
    op.drop_column('leads', 'segment')
    op.drop_column('leads', 'segmented_at')
    op.drop_column('leads', 'email_subject_a')
    op.drop_column('leads', 'email_body_a')
    op.drop_column('leads', 'email_subject_b')
    op.drop_column('leads', 'email_body_b')
    op.drop_column('leads', 'email_sent')
    op.drop_column('leads', 'email_sent_at')
