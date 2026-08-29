"""Store environment secrets encrypted instead of plain JSON variables."""

from alembic import op
import sqlalchemy as sa


revision = "0004_environment_secrets"
down_revision = "0003_agent_tasks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("test_environments", sa.Column("secrets_encrypted", sa.Text(), nullable=True))
    op.execute(sa.text("UPDATE test_environments SET secrets_encrypted = '' WHERE secrets_encrypted IS NULL"))


def downgrade() -> None:
    op.drop_column("test_environments", "secrets_encrypted")
