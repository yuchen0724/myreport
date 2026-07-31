from pathlib import Path

import yaml

from app.utils.semantic_context import build_semantic_snapshot, load_semantic_schema


def test_inventory_balances_are_marked_semi_additive():
    freedom = next(
        item for item in load_semantic_schema()
        if item["database"] == "ads_cockpit_freedom"
    )

    rules = freedom["semantics"]["semi_additive_metrics"]
    assert rules[0]["non_additive_dimension"] == "dt"
    assert "sum_snapshot_across_time" in freedom["semantics"]["forbidden_patterns"]


def test_semantic_snapshot_instructs_boundary_selection():
    snapshot = build_semantic_snapshot(
        "# 商策自由查 NL2SQL 语义层文档\nads_cockpit_freedom",
        data_source_id=1,
        question="查询本月期初和期末库存",
    )

    assert "semi_additive_metrics" in snapshot
    assert "禁止跨日期直接求和" in snapshot
    assert "latest closing snapshot on or before end" in snapshot


def test_semantic_yaml_is_valid():
    schema_path = Path(__file__).resolve().parents[2] / "semantic" / "semantic_layer.schema.yaml"
    schema = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
    assert schema[0]["semantics"]["semi_additive_metrics"][0]["non_additive_dimension"] == "dt"
