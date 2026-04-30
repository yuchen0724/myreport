# backend/tests/test_async_export.py
import pytest
from unittest.mock import Mock, patch, MagicMock


def test_create_export_task(db_session):
    """测试创建导出任务（使用 mock）"""
    with patch('app.services.async_export_service.export_excel_async') as mock_excel:
        mock_task = Mock()
        mock_task.delay.return_value = Mock(id="test-task-id")
        mock_excel.delay = mock_task.delay
        
        from app.services.async_export_service import AsyncExportService
        from app.schemas.async_export import AsyncExportRequest
        
        service = AsyncExportService(db_session)

        request = AsyncExportRequest(
            data_source_id=1,
            sql="SELECT * FROM users LIMIT 10",
            export_type="excel"
        )

        response = service.create_export_task(request, user_id=1)
        assert response.task_id is not None
        assert response.status == "PENDING"


def test_get_task_status(db_session):
    """测试获取任务状态"""
    from app.services.async_export_service import AsyncExportService
    
    service = AsyncExportService(db_session)
    
    # 查询不存在的任务返回 None
    task = service.get_task_status("non-existent-task")
    assert task is None