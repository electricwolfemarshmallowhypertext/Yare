"""add orgs table and org_id columns"""

from alembic import op
import sqlalchemy as sa

revision = "004_add_orgs_and_org_columns"
down_revision = "003_add_personas"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "orgs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
    )
    with op.batch_alter_table("memories") as bop:
        bop.add_column(sa.Column("org_id", sa.String(), nullable=True))
        bop.create_index("idx_mem_org", ["org_id"], unique=False)
    with op.batch_alter_table("personas") as bop:
        bop.add_column(sa.Column("org_id", sa.String(), nullable=True))
        bop.create_index("idx_persona_org", ["org_id"], unique=False)
    with op.batch_alter_table("api_keys") as bop:
        bop.add_column(sa.Column("org_id", sa.String(), nullable=True))

def downgrade():
    with op.batch_alter_table("api_keys") as bop:
        bop.drop_column("org_id")
    with op.batch_alter_table("personas") as bop:
        bop.drop_index("idx_persona_org")
        bop.drop_column("org_id")
    with op.batch_alter_table("memories") as bop:
        bop.drop_index("idx_mem_org")
        bop.drop_column("org_id")
    op.drop_table("orgs")