from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001_add_resource_configs"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "resource_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("level", sa.String(20), nullable=False),
        sa.Column("data_store_type", sa.String(50), nullable=False),
        sa.Column("config_json", sa.JSON(), default=dict),
        sa.Column("is_default", sa.Boolean(), default=False),
        sa.Column("created_at", sa.DateTime(), default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "dataset_resource_bindings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column(
            "resource_config_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("resource_configs.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), default="active"),
        sa.Column("last_rebuild_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "retrieval_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("query_latency_ms", sa.Integer(), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False),
        sa.Column("retrieval_method", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(), default=sa.func.now()),
    )


def downgrade():
    op.drop_table("retrieval_metrics")
    op.drop_table("dataset_resource_bindings")
    op.drop_table("resource_configs")
