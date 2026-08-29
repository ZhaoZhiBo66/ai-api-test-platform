"""Add environments, runtime workflow, audit and richer results."""

from alembic import op
import sqlalchemy as sa


revision = "0002_runtime_features"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "test_environments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("base_url", sa.Text(), nullable=True),
        sa.Column("variables", sa.JSON(), nullable=True),
        sa.Column("headers", sa.JSON(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_id", sa.String(64), nullable=False),
        sa.Column("actor", sa.String(100), nullable=True),
        sa.Column("role", sa.String(20), nullable=True),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("path", sa.String(500), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("client_ip", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_audit_logs_request_id", "audit_logs", ["request_id"])
    op.add_column("api_interfaces", sa.Column("spec", sa.JSON(), nullable=True))
    op.add_column("test_cases", sa.Column("assertions", sa.JSON(), nullable=True))
    op.add_column("test_cases", sa.Column("extractors", sa.JSON(), nullable=True))
    op.add_column("test_cases", sa.Column("dependencies", sa.JSON(), nullable=True))
    op.add_column("test_cases", sa.Column("request_config", sa.JSON(), nullable=True))
    op.add_column("test_cases", sa.Column("retry_count", sa.Integer(), nullable=True))
    op.add_column("test_cases", sa.Column("enabled", sa.Boolean(), nullable=True))
    op.add_column("test_cases", sa.Column("updated_at", sa.DateTime(), nullable=True))
    with op.batch_alter_table("test_runs") as batch:
        batch.add_column(sa.Column("environment_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_test_runs_environment_id", "test_environments", ["environment_id"], ["id"]
        )
        batch.add_column(sa.Column("variables", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("cancel_requested", sa.Boolean(), nullable=True))
        batch.add_column(sa.Column("started_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("finished_at", sa.DateTime(), nullable=True))
    op.add_column("test_results", sa.Column("response_headers", sa.JSON(), nullable=True))
    op.add_column("test_results", sa.Column("duration_ms", sa.Integer(), nullable=True))
    op.add_column("test_results", sa.Column("extracted_variables", sa.JSON(), nullable=True))
    op.add_column("test_results", sa.Column("attempt", sa.Integer(), nullable=True))
    # Preserve behavior for rows created by the pre-migration application.
    op.execute(sa.text("UPDATE api_interfaces SET spec = '{}' WHERE spec IS NULL"))
    op.execute(
        sa.text(
            "UPDATE test_cases SET assertions = '[]', extractors = '[]', dependencies = '[]', "
            "request_config = '{}', retry_count = 0, enabled = 1, updated_at = created_at"
        )
    )
    op.execute(
        sa.text("UPDATE test_runs SET variables = '{}', cancel_requested = 0 WHERE variables IS NULL")
    )
    op.execute(
        sa.text(
            "UPDATE test_results SET response_headers = '{}', extracted_variables = '{}', attempt = 1 "
            "WHERE response_headers IS NULL"
        )
    )


def downgrade() -> None:
    op.drop_column("test_results", "attempt")
    op.drop_column("test_results", "extracted_variables")
    op.drop_column("test_results", "duration_ms")
    op.drop_column("test_results", "response_headers")
    with op.batch_alter_table("test_runs") as batch:
        batch.drop_column("finished_at")
        batch.drop_column("started_at")
        batch.drop_column("cancel_requested")
        batch.drop_column("variables")
        batch.drop_constraint("fk_test_runs_environment_id", type_="foreignkey")
        batch.drop_column("environment_id")
    op.drop_column("test_cases", "updated_at")
    op.drop_column("test_cases", "enabled")
    op.drop_column("test_cases", "retry_count")
    op.drop_column("test_cases", "request_config")
    op.drop_column("test_cases", "dependencies")
    op.drop_column("test_cases", "extractors")
    op.drop_column("test_cases", "assertions")
    op.drop_column("api_interfaces", "spec")
    op.drop_index("ix_audit_logs_request_id", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_table("test_environments")
