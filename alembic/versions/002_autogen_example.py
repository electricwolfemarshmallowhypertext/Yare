"""autogen example: add priority column and index on created_at"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "002_autogen_example"
down_revision = "001_init_memories_projects"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("memories") as batch_op:
        batch_op.add_column(sa.Column("priority", sa.Integer(), nullable=True))
        batch_op.create_index("idx_mem_created_at", ["created_at"], unique=False)


def downgrade():
    with op.batch_alter_table("memories") as batch_op:
        batch_op.drop_index("idx_mem_created_at")
        batch_op.drop_column("priority")