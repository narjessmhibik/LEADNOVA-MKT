"""add scraped_at and followup fields

Revision ID: b1c2d3e4f5a6
Revises: a1b2c3d4e5f6
Create Date: 2026-06-10

"""
from alembic import op
import sqlalchemy as sa

revision = 'b1c2d3e4f5a6'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('leads', sa.Column('scraped_at', sa.DateTime(), nullable=True))
    op.add_column('leads', sa.Column('followup_sent', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('leads', sa.Column('followup_sent_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('leads', 'scraped_at')
    op.drop_column('leads', 'followup_sent')
    op.drop_column('leads', 'followup_sent_at')
