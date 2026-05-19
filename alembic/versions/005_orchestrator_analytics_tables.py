"""add workflows, workflow_tasks, workflow_events, analytics_results"""

from alembic import op
import sqlalchemy as sa

revision = "005_orchestrator_analytics_tables"
down_revision = "004_add_orgs_and_org_columns"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "workflows",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("org_id", sa.String(), nullable=True),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("spec", sa.Text(), nullable=False),
        sa.Column("started_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )
    op.create_table(
        "workflow_tasks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workflow_id", sa.String(), nullable=False, index=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("started_at", sa.String(), nullable=True),
        sa.Column("finished_at", sa.String(), nullable=True),
    )
    op.create_table(
        "workflow_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workflow_id", sa.String(), nullable=False, index=True),
        sa.Column("ts", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("data", sa.Text(), nullable=False),
    )
    op.create_table(
        "analytics_results",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("data", sa.Text(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
    )


def downgrade():
    op.drop_table("analytics_results")
    op.drop_table("workflow_events")
    op.drop_table("workflow_tasks")
    op.drop_table("workflows")