"""add personas table and api_keys table (if missing)"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "003_add_personas"
down_revision = "002_autogen_example"
branch_labels = None
depends_on = None


def upgrade():
    # personas
    op.create_table(
        "personas",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("data", sa.Text(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
    )

    # api_keys (if not already created by runtime)
    op.create_table(
        "api_keys",
        sa.Column("key_hash", sa.String(), primary_key=True),
        sa.Column("roles", sa.Text(), nullable=False),
        sa.Column("tier", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("revoked_at", sa.String(), nullable=True),
    )


def downgrade():
    op.drop_table("api_keys")
    op.drop_table("personas")