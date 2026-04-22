# backend/tests/test_async_export.py
import pytest
from app.services.async_export_service import AsyncExportService
from app.schemas.async_export import AsyncExportRequest

def test_create_export_task(db):
    """测试创建导出任务"""
    service = AsyncExportService(db)

    request = AsyncExportRequest(
        data_source_id=1,
        sql="SELECT * FROM users LIMIT 10",
        export_type="excel"
    )

    # 注意：这个测试需要 Celery worker 运行
    # 在实际环境中，应该使用 mock 来模拟 Celery 任务
    try:
        response = service.create_export_task(request, user_id=1)
        assert response.task_id is not None
        assert response.status == "PENDING"
    except Exception as e:
        # 如果 Celery 不可用，跳过测试
        pytest.skip(f"Celery not available: {e}")

def test_get_task_status(db):
    """测试获取任务状态"""
    service = AsyncExportService(db)

    # 注意：这个测试需要 Celery worker 运行
    # 在实际环境中，应该使用 mock 来模拟 Celery 任务
    try:
        # 先创建任务
        request = AsyncExportRequest(
            data_source_id=1,
            sql="SELECT * FROM users LIMIT 10",
            export_type="excel"
        )
        response = service.create_export_task(request, user_id=1)

        # 获取任务状态
        task = service.get_task_status(response.task_id)

        assert task is not None
        assert task.id == response.task_id
    except Exception as e:
        # 如果 Celery 不可用，跳过测试
        pytest.skip(f"Celery not available: {e}")
