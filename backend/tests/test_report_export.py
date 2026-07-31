from unittest.mock import MagicMock, patch

from openpyxl import load_workbook

from app.schemas.report import ExcelExportRequest
from app.services.report_service import ReportService


def test_excel_export_writes_every_bounded_row(db_session):
    service = ReportService(db_session)
    service.query_service = MagicMock()
    rows = [[index, f"商品-{index}"] for index in range(120)]
    service.query_service.execute_export_sql.return_value = (
        ["id", "name"], rows, len(rows)
    )
    request = ExcelExportRequest(
        data_source_id=1,
        sql="SELECT id, name FROM stock WHERE dt >= ${start_date}",
        params={"start_date": "2026-07-01"},
    )

    output = service.generate_excel(request, user_id=7)

    workbook = load_workbook(output, read_only=True)
    values = list(workbook.active.values)
    workbook.close()
    assert values[0] == ("id", "name")
    assert values[1:] == [tuple(row) for row in rows]
    assert service.last_row_count == 120
    service.query_service.execute_export_sql.assert_called_once_with(
        1,
        request.sql,
        7,
        params={"start_date": "2026-07-01"},
        max_rows=service.settings.export_max_rows,
    )


def test_async_excel_export_forwards_query_params(db_session, test_user):
    service = ReportService(db_session)
    request = ExcelExportRequest(
        data_source_id=1,
        sql="SELECT * FROM stock WHERE dt BETWEEN ${start_date} AND ${end_date}",
        params={"start_date": "2026-07-01", "end_date": "2026-07-31"},
    )

    with patch("app.tasks.export_tasks.export_excel_async.delay") as delay:
        task_id = service.generate_excel_async(request, test_user.id)

    delay.assert_called_once_with(
        task_id,
        1,
        request.sql,
        test_user.id,
        request.params,
    )
