from app.schemas.inventory_copilot import InventoryCopilotRequest
from app.services.inventory_copilot_service import InventoryCopilotService


def _request(**overrides):
    payload = {
        "data_source_id": 1,
        "table_name": "uup_catalog.ads_data.inventory_daily",
        "start_date": "2026-07-01",
        "end_date": "2026-07-30",
        "dimensions": ["store_id", "sku_id"],
        "entity_keys": ["store_id", "sku_id", "batch_id"],
        "fields": {
            "date_field": "dt",
            "closing_stock_field": "end_stock_num",
            "sales_field": "sale_num",
            "receipt_field": "receive_num",
        },
        "include_ai_summary": False,
    }
    payload.update(overrides)
    return InventoryCopilotRequest(**payload)


def test_query_selects_boundary_snapshots_before_aggregation():
    sql, params = InventoryCopilotService.build_query(_request())

    assert "ROW_NUMBER() OVER (PARTITION BY store_id, sku_id, batch_id ORDER BY dt DESC)" in sql
    assert "WHERE dt < :start_date" in sql
    assert "WHERE dt <= :end_date" in sql
    assert "FROM opening_ranked WHERE rn = 1" in sql
    assert "FROM closing_ranked WHERE rn = 1" in sql
    assert "SUM(COALESCE(end_stock_num, 0))" not in sql
    assert params == {"start_date": "2026-07-01", "end_date": "2026-07-30"}


def test_explicit_opening_field_uses_start_date_only():
    request = _request(fields={
        "date_field": "dt",
        "opening_stock_field": "begin_stock_num",
        "closing_stock_field": "end_stock_num",
        "sales_field": "sale_num",
        "receipt_field": "receive_num",
    })
    sql, _ = InventoryCopilotService.build_query(request)
    assert "begin_stock_num AS snapshot_qty" in sql
    assert "WHERE dt = :start_date" in sql


def test_decisions_and_balance_check_are_deterministic(db_session):
    service = InventoryCopilotService(db_session)
    request = _request(stockout_cover_days=7, overstock_cover_days=60)
    records = [
        {
            "store_id": "S1", "sku_id": "A", "opening_qty": 10,
            "receipt_qty": 5, "other_inbound_qty": 0, "sales_qty": 20,
            "other_outbound_qty": 0, "closing_qty": 0,
        },
        {
            "store_id": "S1", "sku_id": "B", "opening_qty": 100,
            "receipt_qty": 0, "other_inbound_qty": 0, "sales_qty": 0,
            "other_outbound_qty": 0, "closing_qty": 100,
        },
    ]

    evidence = service._evaluate(records, request)
    assert evidence["summary"]["stockout"] == 1
    assert evidence["summary"]["slow_moving"] == 1
    assert evidence["summary"]["balance_mismatch"] == 1


def test_dimensions_must_be_part_of_entity_grain():
    try:
        _request(dimensions=["category_id"])
    except ValueError as exc:
        assert "实体键" in str(exc)
    else:
        raise AssertionError("invalid grain should fail")
