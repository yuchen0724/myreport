# backend/tests/test_review.py
"""SQL 审核工作流 API 测试"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.user import User
from app.models.role import Role
from app.models.template import Template
from app.models.sql_review import SqlReview
from app.core.security import get_password_hash, create_access_token


def _setup_role(db_session, role_name="admin"):
    """确保角色存在"""
    role = db_session.query(Role).filter(Role.name == role_name).first()
    if not role:
        role = Role(name=role_name, description=f"{role_name} role")
        db_session.add(role)
        db_session.commit()
        db_session.refresh(role)
    return role


def _create_user(db_session, username, email, role_name=None, suffix=""):
    """创建用户并可选地分配角色"""
    user = User(
        username=f"{username}{suffix}",
        email=f"{email}{suffix}@example.com",
        password_hash=get_password_hash("test123"),
        is_active=True,
    )
    if role_name:
        role = _setup_role(db_session, role_name)
        user.role_id = role.id
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _create_template(db_session, user_id):
    tpl = Template(
        name="审核测试模板",
        config='{"sql": "SELECT 1"}',
        created_by=user_id,
    )
    db_session.add(tpl)
    db_session.commit()
    db_session.refresh(tpl)
    return tpl


def _login_headers(user, db_session):
    """获取指定用户的认证头"""
    token = create_access_token(data={"sub": user.username, "user_id": user.id})
    return {"Authorization": f"Bearer {token}"}


# ==================================================================
# 提交审核
# ==================================================================

class TestCreateReview:
    def test_submit_review(self, client: TestClient, db_session):
        """普通用户提交审核工单"""
        user = _create_user(db_session, "reviewer_u", "ru", suffix="_a")
        tpl = _create_template(db_session, user.id)
        headers = _login_headers(user, db_session)

        resp = client.post(
            "/api/reviews",
            json={"template_id": tpl.id, "sql_content": "SELECT * FROM orders"},
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "pending"
        assert data["template_id"] == tpl.id
        assert data["ai_risk_level"] == "high"
        assert data["ai_review"]["human_approval_required"] is True

    def test_submit_review_invalid_template(self, client: TestClient, db_session):
        """提交不存在的模板应返回 400"""
        user = _create_user(db_session, "reviewer_u2", "ru2", suffix="_b")
        headers = _login_headers(user, db_session)

        resp = client.post(
            "/api/reviews",
            json={"template_id": 99999},
            headers=headers,
        )
        assert resp.status_code == 400

    def test_submit_review_unauthenticated(self, client: TestClient, db_session):
        """未登录应返回 401"""
        resp = client.post("/api/reviews", json={"template_id": 1})
        assert resp.status_code == 401


# ==================================================================
# 查询
# ==================================================================

class TestListReviews:
    def test_list_reviews(self, client: TestClient, db_session):
        """管理员可查看审核列表"""
        admin = _create_user(db_session, "admin_u", "adm", role_name="admin", suffix="_c")
        user = _create_user(db_session, "list_u", "lu", suffix="_d")
        tpl = _create_template(db_session, admin.id)

        # 提交一条
        user_headers = _login_headers(user, db_session)
        client.post(
            "/api/reviews",
            json={"template_id": tpl.id, "sql_content": "SELECT 2"},
            headers=user_headers,
        )

        # 查询
        admin_headers = _login_headers(admin, db_session)
        resp = client.get("/api/reviews", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    def test_filter_by_status(self, client: TestClient, db_session):
        """按状态过滤"""
        admin = _create_user(db_session, "filter_a", "fa", role_name="admin", suffix="_e")
        tpl = _create_template(db_session, admin.id)
        user = _create_user(db_session, "filter_u", "fu", suffix="_f")
        user_headers = _login_headers(user, db_session)
        client.post("/api/reviews", json={"template_id": tpl.id}, headers=user_headers)

        admin_headers = _login_headers(admin, db_session)
        resp = client.get("/api/reviews?status=pending", headers=admin_headers)
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["status"] == "pending"

    def test_get_review_detail(self, client: TestClient, db_session):
        """获取审核详情"""
        user = _create_user(db_session, "detail_u", "du", suffix="_g")
        tpl = _create_template(db_session, user.id)
        user_headers = _login_headers(user, db_session)

        create_resp = client.post(
            "/api/reviews",
            json={"template_id": tpl.id, "sql_content": "SELECT 3"},
            headers=user_headers,
        )
        review_id = create_resp.json()["id"]

        resp = client.get(f"/api/reviews/{review_id}", headers=user_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == review_id

    def test_get_nonexistent_review(self, client: TestClient, db_session):
        """查询不存在的工单应返回 404"""
        user = _create_user(db_session, "miss_u", "mu", suffix="_h")
        headers = _login_headers(user, db_session)
        resp = client.get("/api/reviews/99999", headers=headers)
        assert resp.status_code == 404


# ==================================================================
# 审核操作（仅管理员）
# ==================================================================

class TestReviewAction:
    def test_approve_review(self, client: TestClient, db_session):
        """管理员审核通过"""
        admin = _create_user(db_session, "appr_admin", "apa", role_name="admin", suffix="_k")
        user = _create_user(db_session, "appr_user", "apu", suffix="_l")
        tpl = _create_template(db_session, admin.id)

        user_headers = _login_headers(user, db_session)
        resp = client.post(
            "/api/reviews",
            json={"template_id": tpl.id, "sql_content": "SELECT 5"},
            headers=user_headers,
        )
        review_id = resp.json()["id"]

        admin_headers = _login_headers(admin, db_session)
        resp = client.put(
            f"/api/reviews/{review_id}/review",
            json={"status": "approved", "review_comment": "SQL 无问题"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["review_comment"] == "SQL 无问题"
        assert data["reviewed_at"] is not None

    def test_reject_review(self, client: TestClient, db_session):
        """管理员审核拒绝"""
        admin = _create_user(db_session, "rej_admin", "rea", role_name="admin", suffix="_m")
        user = _create_user(db_session, "rej_user", "reu", suffix="_n")
        tpl = _create_template(db_session, admin.id)

        user_headers = _login_headers(user, db_session)
        resp = client.post(
            "/api/reviews",
            json={"template_id": tpl.id, "sql_content": "DELETE FROM users"},
            headers=user_headers,
        )
        review_id = resp.json()["id"]

        admin_headers = _login_headers(admin, db_session)
        resp = client.put(
            f"/api/reviews/{review_id}/review",
            json={"status": "rejected", "review_comment": "禁止删除用户表"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    def test_non_admin_cannot_review(self, client: TestClient, db_session):
        """非管理员不能审核"""
        user = _create_user(db_session, "nonadm_u", "nu", suffix="_o")
        admin = _create_user(db_session, "nonadm_a", "na", role_name="admin", suffix="_p")
        tpl = _create_template(db_session, admin.id)

        user_headers = _login_headers(user, db_session)
        resp = client.post(
            "/api/reviews",
            json={"template_id": tpl.id},
            headers=user_headers,
        )
        review_id = resp.json()["id"]

        resp = client.put(
            f"/api/reviews/{review_id}/review",
            json={"status": "approved"},
            headers=user_headers,
        )
        assert resp.status_code == 403

    def test_cannot_review_twice(self, client: TestClient, db_session):
        """已审核的工单不可重复审核"""
        admin = _create_user(db_session, "twice_a", "ta", role_name="admin", suffix="_q")
        user = _create_user(db_session, "twice_u", "tu", suffix="_r")
        tpl = _create_template(db_session, admin.id)

        user_headers = _login_headers(user, db_session)
        resp = client.post(
            "/api/reviews",
            json={"template_id": tpl.id},
            headers=user_headers,
        )
        review_id = resp.json()["id"]

        admin_headers = _login_headers(admin, db_session)
        # 第一次通过
        client.put(
            f"/api/reviews/{review_id}/review",
            json={"status": "approved"},
            headers=admin_headers,
        )
        # 第二次应失败
        resp = client.put(
            f"/api/reviews/{review_id}/review",
            json={"status": "rejected"},
            headers=admin_headers,
        )
        assert resp.status_code in [400, 409]


# ==================================================================
# 删除审核工单
# ==================================================================

class TestDeleteReview:
    def test_delete_pending_review(self, client: TestClient, db_session):
        """提交者可删除待审核工单"""
        user = _create_user(db_session, "del_u", "du2", suffix="_s")
        tpl = _create_template(db_session, user.id)
        headers = _login_headers(user, db_session)

        resp = client.post("/api/reviews", json={"template_id": tpl.id}, headers=headers)
        review_id = resp.json()["id"]

        resp = client.delete(f"/api/reviews/{review_id}", headers=headers)
        assert resp.status_code == 204

    def test_cannot_delete_others_review(self, client: TestClient, db_session):
        """不能删除他人的工单"""
        user1 = _create_user(db_session, "del1", "d1", suffix="_t")
        user2 = _create_user(db_session, "del2", "d2", suffix="_u")
        tpl = _create_template(db_session, user1.id)
        headers1 = _login_headers(user1, db_session)
        headers2 = _login_headers(user2, db_session)

        resp = client.post("/api/reviews", json={"template_id": tpl.id}, headers=headers1)
        review_id = resp.json()["id"]

        resp = client.delete(f"/api/reviews/{review_id}", headers=headers2)
        assert resp.status_code == 403

    def test_cannot_delete_reviewed(self, client: TestClient, db_session):
        """已审核的工单不可删除"""
        admin = _create_user(db_session, "drev_a", "da2", role_name="admin", suffix="_v")
        user = _create_user(db_session, "drev_u", "du3", suffix="_w")
        tpl = _create_template(db_session, admin.id)
        user_headers = _login_headers(user, db_session)
        admin_headers = _login_headers(admin, db_session)

        resp = client.post("/api/reviews", json={"template_id": tpl.id}, headers=user_headers)
        review_id = resp.json()["id"]

        # 管理员审核
        client.put(
            f"/api/reviews/{review_id}/review",
            json={"status": "approved"},
            headers=admin_headers,
        )

        # 提交者尝试删除
        resp = client.delete(f"/api/reviews/{review_id}", headers=user_headers)
        assert resp.status_code == 400


# ==================================================================
# Pagination
# ==================================================================

class TestPagination:
    def test_pagination(self, client: TestClient, db_session):
        """分页测试"""
        user = _create_user(db_session, "pg_u", "pgu", suffix="_x")
        tpl = _create_template(db_session, user.id)
        headers = _login_headers(user, db_session)

        # 提交 3 条
        for i in range(3):
            client.post(
                "/api/reviews",
                json={"template_id": tpl.id, "sql_content": f"SELECT {i}"},
                headers=headers,
            )

        resp = client.get("/api/reviews?page=1&page_size=2", headers=headers)
        data = resp.json()
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert data["total"] == 3
        assert data["total_pages"] == 2
        assert len(data["items"]) == 2
