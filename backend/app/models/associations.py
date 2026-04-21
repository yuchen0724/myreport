from sqlalchemy import Column, Integer, ForeignKey, Table
from sqlalchemy.orm import registry

# 创建关联表
mapper_registry = registry()

role_permissions = Table(
    "role_permissions",
    mapper_registry.metadata,
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", Integer, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)
