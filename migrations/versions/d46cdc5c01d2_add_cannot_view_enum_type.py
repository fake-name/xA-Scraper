"""Add cannot view enum type

Revision ID: d46cdc5c01d2
Revises: 9a7aef735c43
Create Date: 2025-12-06 20:25:05.798427

"""

# revision identifiers, used by Alembic.
revision = 'd46cdc5c01d2'
down_revision = '9a7aef735c43'

from alembic import op
import sqlalchemy as sa
import sqlalchemy_jsonfield



def upgrade():
    op.execute("COMMIT")
    op.execute("ALTER TYPE dlstate_enum ADD VALUE 'cannot_view';")
    pass


def downgrade():
    pass
