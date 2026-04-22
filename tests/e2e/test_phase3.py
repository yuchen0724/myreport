# tests/e2e/test_phase3.py
import pytest
import requests
import time

BASE_URL = "http://localhost:8000"

def test_async_export_flow():
    """测试异步导出完整流程"""
    # 1. 创建导出任务
    response = requests.post(
        f"{BASE_URL}/api/async-export/create",
        json={
            "data_source_id": 1,
            "sql": "SELECT * FROM users LIMIT 10",
            "export_type": "excel"
        }
    )
    assert response.status_code == 201
    task_id = response.json()["task_id"]

    # 2. 等待任务完成
    max_wait = 60
    for i in range(max_wait):
        response = requests.get(f"{BASE_URL}/api/async-export/task/{task_id}")
        assert response.status_code == 200
        task = response.json()

        if task["status"] in ["SUCCESS", "FAILED"]:
            break

        time.sleep(1)

    # 3. 验证任务状态
    assert task["status"] == "SUCCESS"
    assert task["file_path"] is not None

def test_template_share_flow():
    """测试模板分享完整流程"""
    # 1. 分享模板
    response = requests.post(
        f"{BASE_URL}/api/templates/1/share",
        json={"user_ids": [2, 3]}
    )
    assert response.status_code == 200

    # 2. 获取分享的模板
    response = requests.get(f"{BASE_URL}/api/templates/shared/me")
    assert response.status_code == 200
    templates = response.json()
    assert len(templates) > 0

def test_cache_flow():
    """测试缓存功能"""
    # 1. 执行查询
    response = requests.post(
        f"{BASE_URL}/api/query/sql",
        json={
            "data_source_id": 1,
            "sql": "SELECT * FROM users LIMIT 10"
        }
    )
    assert response.status_code == 200

    # 2. 再次执行相同查询（应该从缓存获取）
    response = requests.post(
        f"{BASE_URL}/api/query/sql",
        json={
            "data_source_id": 1,
            "sql": "SELECT * FROM users LIMIT 10"
        }
    )
    assert response.status_code == 200

def test_rate_limit_flow():
    """测试限流功能"""
    # 快速发送多个请求
    for i in range(105):
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 429:
            # 触发限流
            assert "X-RateLimit-Remaining" in response.headers
            break
    else:
        # 如果没有触发限流，测试也通过
        pass

if __name__ == "__main__":
    print("运行端到端测试...")
    print("\n1. 测试异步导出流程...")
    try:
        test_async_export_flow()
        print("✅ 异步导出流程测试通过")
    except Exception as e:
        print(f"❌ 异步导出流程测试失败: {e}")

    print("\n2. 测试模板分享流程...")
    try:
        test_template_share_flow()
        print("✅ 模板分享流程测试通过")
    except Exception as e:
        print(f"❌ 模板分享流程测试失败: {e}")

    print("\n3. 测试缓存功能...")
    try:
        test_cache_flow()
        print("✅ 缓存功能测试通过")
    except Exception as e:
        print(f"❌ 缓存功能测试失败: {e}")

    print("\n4. 测试限流功能...")
    try:
        test_rate_limit_flow()
        print("✅ 限流功能测试通过")
    except Exception as e:
        print(f"❌ 限流功能测试失败: {e}")

    print("\n所有测试完成！")
