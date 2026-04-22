#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第三阶段端到端测试
测试模板分享、版本对比、异步导出等功能
"""

import requests
import json
import time
from typing import Dict, Any, Optional

# 配置
BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api"

# 测试数据
TEST_USER = {
    "username": "test_user",
    "password": "test_password"
}

TEST_TEMPLATE = {
    "name": "测试模板",
    "description": "测试模板描述",
    "sql": "SELECT * FROM test_table",
    "layout": {"type": "table"},
    "style": {"theme": "default"}
}


class APIClient:
    """API 客户端"""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session = requests.Session()
        self.token: Optional[str] = None

    def login(self, username: str, password: str) -> bool:
        """登录"""
        try:
            response = self.session.post(
                f"{self.base_url}/auth/login",
                json={"username": username, "password": password}
            )
            if response.status_code == 200:
                data = response.json()
                self.token = data.get("access_token")
                self.session.headers.update({
                    "Authorization": f"Bearer {self.token}"
                })
                print(f"✓ 登录成功: {username}")
                return True
            else:
                print(f"✗ 登录失败: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"✗ 登录异常: {e}")
            return False

    def get(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """GET 请求"""
        try:
            response = self.session.get(
                f"{self.base_url}{endpoint}",
                params=params
            )
            if response.status_code == 200:
                return response.json()
            else:
                print(f"✗ GET {endpoint} 失败: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"✗ GET {endpoint} 异常: {e}")
            return None

    def post(self, endpoint: str, data: Optional[Dict] = None) -> Optional[Dict]:
        """POST 请求"""
        try:
            response = self.session.post(
                f"{self.base_url}{endpoint}",
                json=data
            )
            if response.status_code in [200, 201]:
                return response.json()
            else:
                print(f"✗ POST {endpoint} 失败: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"✗ POST {endpoint} 异常: {e}")
            return None

    def put(self, endpoint: str, data: Optional[Dict] = None) -> Optional[Dict]:
        """PUT 请求"""
        try:
            response = self.session.put(
                f"{self.base_url}{endpoint}",
                json=data
            )
            if response.status_code == 200:
                return response.json()
            else:
                print(f"✗ PUT {endpoint} 失败: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"✗ PUT {endpoint} 异常: {e}")
            return None

    def delete(self, endpoint: str) -> bool:
        """DELETE 请求"""
        try:
            response = self.session.delete(f"{self.base_url}{endpoint}")
            if response.status_code == 204:
                return True
            else:
                print(f"✗ DELETE {endpoint} 失败: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"✗ DELETE {endpoint} 异常: {e}")
            return False


def test_template_share(client: APIClient) -> bool:
    """测试模板分享功能"""
    print("\n=== 测试模板分享功能 ===")

    # 1. 创建测试模板
    print("1. 创建测试模板...")
    template = client.post("/api/templates", TEST_TEMPLATE)
    if not template:
        print("✗ 创建模板失败")
        return False
    template_id = template.get("id")
    print(f"✓ 创建模板成功: ID={template_id}")

    # 2. 获取用户列表
    print("2. 获取用户列表...")
    users = client.get("/api/users")
    if not users:
        print("✗ 获取用户列表失败")
        return False
    print(f"✓ 获取用户列表成功: {len(users)} 个用户")

    # 3. 分享模板
    if len(users) > 0:
        share_user_id = users[0].get("id")
        print(f"3. 分享模板给用户 {share_user_id}...")
        share_result = client.post(
            f"/api/templates/{template_id}/share",
            {"user_id": share_user_id}
        )
        if not share_result:
            print("✗ 分享模板失败")
            return False
        print("✓ 分享模板成功")

    # 4. 获取分享给我的模板
    print("4. 获取分享给我的模板...")
    shared_templates = client.get("/api/templates/shared")
    if shared_templates is None:
        print("✗ 获取分享模板失败")
        return False
    print(f"✓ 获取分享模板成功: {len(shared_templates)} 个模板")

    # 5. 获取模板分享详情
    print("5. 获取模板分享详情...")
    share_details = client.get(f"/api/templates/{template_id}/shares")
    if share_details is None:
        print("✗ 获取分享详情失败")
        return False
    print(f"✓ 获取分享详情成功: {len(share_details)} 条记录")

    # 6. 清理测试数据
    print("6. 清理测试数据...")
    if client.delete(f"/api/templates/{template_id}"):
        print("✓ 删除模板成功")
    else:
        print("⚠ 删除模板失败")

    return True


def test_version_diff(client: APIClient) -> bool:
    """测试版本对比功能"""
    print("\n=== 测试版本对比功能 ===")

    # 1. 创建测试模板
    print("1. 创建测试模板...")
    template = client.post("/api/templates", TEST_TEMPLATE)
    if not template:
        print("✗ 创建模板失败")
        return False
    template_id = template.get("id")
    print(f"✓ 创建模板成功: ID={template_id}")

    # 2. 更新模板（创建版本2）
    print("2. 更新模板（创建版本2）...")
    updated_template = client.put(
        f"/api/templates/{template_id}",
        {**TEST_TEMPLATE, "name": "测试模板 v2"}
    )
    if not updated_template:
        print("✗ 更新模板失败")
        return False
    print("✓ 更新模板成功")

    # 3. 获取版本列表
    print("3. 获取版本列表...")
    versions = client.get(f"/api/templates/{template_id}/versions")
    if not versions or len(versions) < 2:
        print("✗ 获取版本列表失败或版本不足")
        return False
    print(f"✓ 获取版本列表成功: {len(versions)} 个版本")

    # 4. 获取版本差异
    print("4. 获取版本差异...")
    version1 = versions[0].get("version")
    version2 = versions[1].get("version")
    diff = client.get(
        f"/api/templates/{template_id}/versions/diff",
        {"version1": version1, "version2": version2}
    )
    if not diff:
        print("✗ 获取版本差异失败")
        return False
    print(f"✓ 获取版本差异成功: v{version1} vs v{version2}")

    # 5. 清理测试数据
    print("5. 清理测试数据...")
    if client.delete(f"/api/templates/{template_id}"):
        print("✓ 删除模板成功")
    else:
        print("⚠ 删除模板失败")

    return True


def test_async_export(client: APIClient) -> bool:
    """测试异步导出功能"""
    print("\n=== 测试异步导出功能 ===")

    # 1. 创建测试模板
    print("1. 创建测试模板...")
    template = client.post("/api/templates", TEST_TEMPLATE)
    if not template:
        print("✗ 创建模板失败")
        return False
    template_id = template.get("id")
    print(f"✓ 创建模板成功: ID={template_id}")

    # 2. 创建异步导出任务
    print("2. 创建异步导出任务...")
    export_task = client.post(
        "/api/exports",
        {
            "template_id": template_id,
            "format": "xlsx",
            "params": {}
        }
    )
    if not export_task:
        print("✗ 创建导出任务失败")
        return False
    task_id = export_task.get("id")
    print(f"✓ 创建导出任务成功: ID={task_id}")

    # 3. 获取导出任务列表
    print("3. 获取导出任务列表...")
    tasks = client.get("/api/exports")
    if not tasks:
        print("✗ 获取导出任务列表失败")
        return False
    print(f"✓ 获取导出任务列表成功: {len(tasks)} 个任务")

    # 4. 获取导出任务详情
    print("4. 获取导出任务详情...")
    task_detail = client.get(f"/api/exports/{task_id}")
    if not task_detail:
        print("✗ 获取导出任务详情失败")
        return False
    print(f"✓ 获取导出任务详情成功: 状态={task_detail.get('status')}")

    # 5. 清理测试数据
    print("5. 清理测试数据...")
    if client.delete(f"/api/templates/{template_id}"):
        print("✓ 删除模板成功")
    else:
        print("⚠ 删除模板失败")

    return True


def test_health_check(client: APIClient) -> bool:
    """测试健康检查"""
    print("\n=== 测试健康检查 ===")

    try:
        response = client.session.get(f"{client.base_url}/health")
        if response.status_code == 200:
            print("✓ 健康检查通过")
            return True
        else:
            print(f"✗ 健康检查失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ 健康检查异常: {e}")
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("第三阶段端到端测试")
    print("=" * 60)

    # 创建 API 客户端
    client = APIClient(API_BASE)

    # 测试健康检查
    if not test_health_check(client):
        print("\n✗ 健康检查失败，请确保服务已启动")
        return

    # 登录
    print("\n=== 登录 ===")
    if not client.login(TEST_USER["username"], TEST_USER["password"]):
        print("\n✗ 登录失败，请检查用户名和密码")
        return

    # 运行测试
    results = {
        "模板分享": test_template_share(client),
        "版本对比": test_version_diff(client),
        "异步导出": test_async_export(client)
    }

    # 输出结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    for test_name, result in results.items():
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{test_name}: {status}")

    # 统计
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    print(f"\n总计: {passed}/{total} 通过")

    if passed == total:
        print("\n✓ 所有测试通过！")
    else:
        print(f"\n✗ {total - passed} 个测试失败")


if __name__ == "__main__":
    main()
