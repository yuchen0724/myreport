"""测试用户创建脚本 - 为端到端测试准备测试用户"""
import sys
import os

# 确保 backend 目录在路径中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.database import SessionLocal
from app.repositories.user_repository import UserRepository

TEST_USER = {
    "username": "test_user",
    "password": "test123",
    "email": "test@example.com",
}


def setup():
    db = SessionLocal()
    try:
        repo = UserRepository(db)
        existing = repo.get_by_username(TEST_USER["username"])
        if existing:
            print(f"测试用户已存在: ID={existing.id}")
            # 先删除再重建（密码可能不对）
            repo.delete(existing)
            db.commit()
            print("已删除旧用户")

        # 注意：create 内部会调用 get_password_hash，这里传明文密码
        user = repo.create({
            "username": TEST_USER["username"],
            "email": TEST_USER["email"],
            "password": TEST_USER["password"],
            "is_active": True,
        })
        print(f"测试用户创建成功: ID={user.id}, username={user.username}")

        # 验证密码
        authed = repo.authenticate(TEST_USER["username"], TEST_USER["password"])
        if authed:
            print("✓ 密码验证通过")
        else:
            print("✗ 密码验证失败！！！")
    except Exception as e:
        print(f"创建测试用户失败: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    setup()
