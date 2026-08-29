"""Replace the experimental agent with reusable regression suites."""

from alembic import op
import sqlalchemy as sa


revision = "0005_regression_suites"
down_revision = "0004_environment_secrets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "test_suites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("fail_fast", sa.Boolean(), nullable=True),
        sa.Column("analyze_by_ai", sa.Boolean(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "test_suite_cases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "suite_id",
            sa.Integer(),
            sa.ForeignKey("test_suites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "case_id",
            sa.Integer(),
            sa.ForeignKey("test_cases.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.UniqueConstraint("suite_id", "case_id", name="uq_suite_case"),
    )
    op.create_index("ix_test_suite_cases_suite_id", "test_suite_cases", ["suite_id"])
    op.create_index("ix_test_suite_cases_case_id", "test_suite_cases", ["case_id"])
    with op.batch_alter_table("test_runs") as batch:
        batch.add_column(sa.Column("suite_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_test_runs_suite_id", "test_suites", ["suite_id"], ["id"])
    op.drop_table("agent_steps")
    op.drop_table("agent_tasks")


def downgrade() -> None:
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
    with op.batch_alter_table("test_runs") as batch:
        batch.drop_constraint("fk_test_runs_suite_id", type_="foreignkey")
        batch.drop_column("suite_id")
    op.drop_index("ix_test_suite_cases_case_id", table_name="test_suite_cases")
    op.drop_index("ix_test_suite_cases_suite_id", table_name="test_suite_cases")
    op.drop_table("test_suite_cases")
    op.drop_table("test_suites")
