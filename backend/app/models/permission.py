from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)
    resource = Column(String(50), nullable=False)
    action = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)

    roles = relationship("Role", secondary="role_permissions", back_populates="permissions")


# 关联表
role_permissions = Base.metadata.tables.get("role_permissions")
if role_permissions is None:
    from sqlalchemy import Table, MetaData
    metadata = MetaData()
    role_permissions = Table(
        "role_permissions",
        metadata,
        Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
        Column("permission_id", Integer, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
    )
