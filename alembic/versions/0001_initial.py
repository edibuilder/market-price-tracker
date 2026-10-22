"""initial schema

Revision ID: 0001
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "tracked_queries",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("query", sa.String(200), nullable=False),
        sa.Column("marketplace", sa.String(20), nullable=False),
        sa.Column("max_items", sa.Integer, nullable=False),
        sa.Column("active", sa.Boolean, nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.UniqueConstraint("query", "marketplace", name="uq_query_marketplace"),
    )
    op.create_table(
        "products",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("external_id", sa.String(100), nullable=False),
        sa.Column("query_id", sa.Integer, sa.ForeignKey("tracked_queries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("category", sa.String(200)),
        sa.Column("condition", sa.String(60)),
        sa.Column("image_url", sa.String(1000)),
        sa.Column("item_url", sa.String(1000)),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("updated_at", TS, nullable=False),
        sa.UniqueConstraint("source", "external_id", name="uq_source_external_id"),
    )
    op.create_index("ix_products_query_id", "products", ["query_id"])
    op.create_table(
        "price_snapshots",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("product_id", sa.Integer, sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("captured_at", TS, nullable=False),
    )
    op.create_index("ix_price_snapshots_product_id", "price_snapshots", ["product_id"])
    op.create_index("ix_price_snapshots_captured_at", "price_snapshots", ["captured_at"])
    op.create_table(
        "query_stats",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("query_id", sa.Integer, sa.ForeignKey("tracked_queries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("captured_at", TS, nullable=False),
        sa.Column("listing_count", sa.Integer, nullable=False),
        sa.Column("min_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("median_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("avg_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("max_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
    )
    op.create_index("ix_query_stats_query_id", "query_stats", ["query_id"])
    op.create_index("ix_query_stats_captured_at", "query_stats", ["captured_at"])


def downgrade() -> None:
    for t in ("query_stats", "price_snapshots", "products", "tracked_queries"):
        op.drop_table(t)
