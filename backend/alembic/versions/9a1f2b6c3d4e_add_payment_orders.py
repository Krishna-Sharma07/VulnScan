"""add payment_orders

Revision ID: 9a1f2b6c3d4e
Revises: 56f270fd0d93
Create Date: 2026-08-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '9a1f2b6c3d4e'
down_revision: Union[str, None] = '56f270fd0d93'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'payment_orders',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        # create_type=False - the "plantier" enum type already exists in
        # Postgres (created by the initial migration for users.plan); this
        # column reuses it rather than trying to CREATE TYPE a second time.
        sa.Column(
            'plan',
            postgresql.ENUM('free', 'pro', 'enterprise', name='plantier', create_type=False),
            nullable=False,
        ),
        sa.Column('razorpay_order_id', sa.String(), nullable=False),
        sa.Column('amount_paise', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(), nullable=False),
        sa.Column(
            'status',
            sa.Enum('created', 'paid', 'failed', name='paymentorderstatus'),
            nullable=False,
        ),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_payment_orders_user_id'), 'payment_orders', ['user_id'], unique=False
    )
    op.create_index(
        op.f('ix_payment_orders_razorpay_order_id'),
        'payment_orders',
        ['razorpay_order_id'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_payment_orders_razorpay_order_id'), table_name='payment_orders')
    op.drop_index(op.f('ix_payment_orders_user_id'), table_name='payment_orders')
    op.drop_table('payment_orders')
    sa.Enum(name='paymentorderstatus').drop(op.get_bind(), checkfirst=True)
