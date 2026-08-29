"""Add bounded, auditable test-agent plans and steps."""

from alembic import op
import sqlalchemy as sa


revision = "0003_agent_tasks"
down_revision = "0002_runtime_features"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=True),
        sa.Column("interface_ids", sa.JSON(), nullable=True),
        sa.Column("environment_id", sa.Integer(), sa.ForeignKey("test_environments.id"), nullable=True),
        sa.Column("plan", sa.JSON(), nullable=True),
        sa.Column("max_steps", sa.Integer(), nullable=True),
        sa.Column("current_step", sa.Integer(), nullable=True),
        sa.Column("use_ai_planner", sa.Boolean(), nullable=True),
        sa.Column("analyze_by_ai", sa.Boolean(), nullable=True),
        sa.Column("cancel_requested", sa.Boolean(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "agent_steps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("agent_tasks.id"), nullable=False),
        sa.Column("step_no", sa.Integer(), nullable=False),
        sa.Column("tool", sa.String(50), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("input_data", sa.JSON(), nullable=True),
        sa.Column("output_data", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("agent_steps")
    op.drop_table("agent_tasks")
