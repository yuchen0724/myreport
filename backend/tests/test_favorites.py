"""收藏夹 API 测试"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.user import User
from app.models.template import Template
from app.models.favorite import Favorite
from app.core.security import get_password_hash


def create_test_user(db_session, suffix=""):
    """创建测试用户"""
    user = User(
        username=f"testuser{suffix}",
        email=f"test{suffix}@example.com",
        password_hash=get_password_hash("test123"),
        role_id=1
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def create_test_template(db_session, user_id):
    """创建测试模板"""
    template = Template(
        name="测试模板",
        config='{"sql": "SELECT * FROM users", "columns": [{"key": "id", "label": "ID"}]}',
        created_by=user_id
    )
    db_session.add(template)
    db_session.commit()
    db_session.refresh(template)
    return template


class TestFavoritesAPI:
    """收藏夹 API 测试"""

    def test_add_favorite(self, client: TestClient, db_session, auth_headers):
        """测试添加收藏"""
        user = create_test_user(db_session, "_fav")
        template = create_test_template(db_session, user.id)

        response = client.post(
            "/api/favorites",
            json={"template_id": template.id, "category": "工作", "note": "常用模板"},
            headers=auth_headers
        )
        assert response.status_code in [200, 201, 204]
        data = response.json()
        assert data["template_id"] == template.id
        assert data["category"] == "工作"

    def test_get_favorites(self, client: TestClient, db_session, auth_headers):
        """测试获取收藏列表"""
        user = create_test_user(db_session, "_fav")
        template = create_test_template(db_session, user.id)

        # 添加收藏
        client.post(
            "/api/favorites",
            json={"template_id": template.id, "category": "默认"},
            headers=auth_headers
        )

        response = client.get("/api/favorites", headers=auth_headers)
        assert response.status_code in [200, 201, 204]
        data = response.json()
        assert len(data) >= 1

    def test_get_favorites_by_category(self, client: TestClient, db_session, auth_headers):
        """测试按分类获取收藏"""
        user = create_test_user(db_session, "_fav")
        template = create_test_template(db_session, user.id)

        client.post(
            "/api/favorites",
            json={"template_id": template.id, "category": "工作"},
            headers=auth_headers
        )

        response = client.get("/api/favorites?category=工作", headers=auth_headers)
        assert response.status_code in [200, 201, 204]
        data = response.json()
        assert all(f["category"] == "工作" for f in data)

    def test_update_favorite(self, client: TestClient, db_session, auth_headers):
        """测试更新收藏"""
        user = create_test_user(db_session, "_fav")
        template = create_test_template(db_session, user.id)

        # 添加收藏
        resp = client.post(
            "/api/favorites",
            json={"template_id": template.id, "category": "默认"},
            headers=auth_headers
        )
        fav_id = resp.json()["id"]

        # 更新收藏
        response = client.put(
            f"/api/favorites/{fav_id}",
            json={"category": "个人", "note": "重要模板"},
            headers=auth_headers
        )
        assert response.status_code in [200, 201, 204]
        assert response.json()["category"] == "个人"

    def test_remove_favorite(self, client: TestClient, db_session, auth_headers):
        """测试删除收藏"""
        user = create_test_user(db_session, "_fav")
        template = create_test_template(db_session, user.id)

        # 添加收藏
        resp = client.post(
            "/api/favorites",
            json={"template_id": template.id},
            headers=auth_headers
        )
        fav_id = resp.json()["id"]

        # 删除收藏
        response = client.delete(f"/api/favorites/{fav_id}", headers=auth_headers)
        assert response.status_code in [200, 201, 204]

    def test_remove_favorite_by_template(self, client: TestClient, db_session, auth_headers):
        """测试按模板 ID 删除收藏"""
        user = create_test_user(db_session, "_fav")
        template = create_test_template(db_session, user.id)

        # 添加收藏
        client.post(
            "/api/favorites",
            json={"template_id": template.id},
            headers=auth_headers
        )

        # 按模板 ID 删除
        response = client.delete(f"/api/favorites/by-template/{template.id}", headers=auth_headers)
        assert response.status_code in [200, 201, 204]

    def test_check_favorite(self, client: TestClient, db_session, auth_headers):
        """测试检查是否已收藏"""
        user = create_test_user(db_session, "_fav")
        template = create_test_template(db_session, user.id)

        # 检查未收藏
        response = client.get(f"/api/favorites/check/{template.id}", headers=auth_headers)
        assert response.status_code in [200, 201, 204]
        assert response.json()["is_favorited"] == False

        # 添加收藏
        client.post(
            "/api/favorites",
            json={"template_id": template.id},
            headers=auth_headers
        )

        # 检查已收藏
        response = client.get(f"/api/favorites/check/{template.id}", headers=auth_headers)
        assert response.status_code in [200, 201, 204]
        assert response.json()["is_favorited"] == True

    def test_duplicate_favorite(self, client: TestClient, db_session, auth_headers):
        """测试重复收藏"""
        user = create_test_user(db_session, "_fav")
        template = create_test_template(db_session, user.id)

        # 第一次添加
        resp1 = client.post(
            "/api/favorites",
            json={"template_id": template.id},
            headers=auth_headers
        )
        assert resp1.status_code in [200, 201]

        # 第二次添加（应该返回已存在）
        resp2 = client.post(
            "/api/favorites",
            json={"template_id": template.id},
            headers=auth_headers
        )
        assert resp2.status_code in [200, 201]  # 应该返回已存在的收藏
