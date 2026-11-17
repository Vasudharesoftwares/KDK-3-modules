"""Add production material recipe master.

Revision ID: d7e4a91c6b20
Revises: c8d4e1a9f203
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d7e4a91c6b20"
down_revision: Union[str, Sequence[str], None] = "c8d4e1a9f203"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "production_material_recipes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(),
                  sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("product_id", sa.Integer(),
                  sa.ForeignKey("products.id"), nullable=False),
        sa.Column("recipe_code", sa.String(60), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("design_code", sa.String(80)),
        sa.Column("basis_quantity", sa.Numeric(16, 3), nullable=False),
        sa.Column("basis_uom_code", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("basis_quantity > 0",
                           name="ck_production_recipe_basis_positive"),
        sa.CheckConstraint(
            "basis_uom_code IN ('metres','pieces','kg')",
            name="ck_production_recipe_basis_uom",
        ),
        sa.UniqueConstraint(
            "company_id", "product_id", "recipe_code", "version",
            name="uq_production_recipe_version",
        ),
    )
    op.create_index(
        "ix_production_recipe_product_active",
        "production_material_recipes",
        ["company_id", "product_id", "is_active"],
    )

    op.create_table(
        "production_material_recipe_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recipe_id", sa.Integer(),
                  sa.ForeignKey("production_material_recipes.id",
                                ondelete="CASCADE"), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("material_product_id", sa.Integer(),
                  sa.ForeignKey("products.id"), nullable=False),
        sa.Column("stock_stage_id", sa.Integer(),
                  sa.ForeignKey("stock_stages.id"), nullable=False),
        sa.Column("quantity_per_basis", sa.Numeric(16, 3), nullable=False),
        sa.Column("quantity_uom_code", sa.String(20), nullable=False),
        sa.Column("wastage_percent", sa.Numeric(7, 3),
                  nullable=False, server_default="0"),
        sa.Column("notes", sa.Text()),
        sa.CheckConstraint(
            "quantity_per_basis > 0",
            name="ck_production_recipe_line_quantity_positive",
        ),
        sa.CheckConstraint(
            "wastage_percent >= 0 AND wastage_percent <= 100",
            name="ck_production_recipe_line_wastage_range",
        ),
        sa.CheckConstraint(
            "quantity_uom_code IN ('metres','pieces','kg')",
            name="ck_production_recipe_line_uom",
        ),
        sa.UniqueConstraint(
            "recipe_id", "line_number",
            name="uq_production_recipe_line_number",
        ),
    )


def downgrade() -> None:
    op.drop_table("production_material_recipe_lines")
    op.drop_index(
        "ix_production_recipe_product_active",
        table_name="production_material_recipes",
    )
    op.drop_table("production_material_recipes")
