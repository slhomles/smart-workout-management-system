"""baseline: lược đồ v1 do database/postgresql/ dựng

Revision ID: 0001_baseline
Revises:
Create Date: 2026-11-26

Revision RỖNG có chủ đích (doc 05 §8.1): lược đồ v1 do `database/postgresql/` (schemas, views, seeds)
dựng và đã đóng băng. Revision này chỉ đánh dấu mốc để các migration sau nối vào.

KHÔNG tự chạy `alembic stamp head` lên DB dùng chung trên VM: Core owner làm tay sau khi báo nhóm.
"""

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
