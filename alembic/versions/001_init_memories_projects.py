"""init memories/projects and project_id index"""

from alembic import op
import sqlalchemy as sa

revision = "001_init_memories_projects"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # base tables if not exist (idempotent patterns vary by DB; Alembic will error if exists)
    op.create_table(
        "memories",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("salience", sa.Float(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("thread_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("persona_id", sa.String(), nullable=False),
        sa.Column("embedding", sa.Text(), nullable=True),
        sa.Column("metadata", sa.Text(), nullable=True),
        sa.Column("project_id", sa.String(), nullable=True),
    )
    op.create_index("idx_mem_thread_persona", "memories", ["thread_id", "persona_id"])
    op.create_index("idx_mem_user", "memories", ["user_id"])
    op.create_index("idx_mem_project", "memories", ["project_id"])

    op.create_table(
        "projects",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
    )

def downgrade():
    op.drop_table("projects")
    op.drop_index("idx_mem_project", table_name="memories")
    op.drop_index("idx_mem_user", table_name="memories")
    op.drop_index("idx_mem_thread_persona", table_name="memories")
    op.drop_table("memories")