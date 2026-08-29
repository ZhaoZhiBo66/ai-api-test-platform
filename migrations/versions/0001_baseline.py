"""Create the original platform schema."""

from alembic import op
import sqlalchemy as sa


revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_interfaces",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("headers", sa.JSON(), nullable=True),
        sa.Column("body", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "test_cases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("interface_id", sa.Integer(), sa.ForeignKey("api_interfaces.id"), nullable=False),
        sa.Column("case_name", sa.String(150), nullable=False),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.Column("expected_status_code", sa.Integer(), nullable=True),
        sa.Column("expected_json", sa.JSON(), nullable=True),
        sa.Column("sql_check", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "test_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("interface_id", sa.Integer(), sa.ForeignKey("api_interfaces.id"), nullable=True),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("total", sa.Integer(), nullable=True),
        sa.Column("passed", sa.Integer(), nullable=True),
        sa.Column("failed", sa.Integer(), nullable=True),
        sa.Column("ai_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "test_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("test_runs.id"), nullable=False),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("test_cases.id"), nullable=False),
        sa.Column("case_name", sa.String(150), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("request_data", sa.JSON(), nullable=True),
        sa.Column("response_data", sa.JSON(), nullable=True),
        sa.Column("assertion_message", sa.Text(), nullable=True),
        sa.Column("ai_analysis", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("test_results")
    op.drop_table("test_runs")
    op.drop_table("test_cases")
    op.drop_table("api_interfaces")
