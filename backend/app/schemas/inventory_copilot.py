"""Inventory copilot request models."""

import re
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
QUALIFIED_IDENTIFIER = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*){0,2}$"
)


class InventoryFieldConfig(BaseModel):
    date_field: str = "dt"
    closing_stock_field: str
    opening_stock_field: Optional[str] = None
    sales_field: Optional[str] = None
    receipt_field: Optional[str] = None
    other_inbound_field: Optional[str] = None
    other_outbound_field: Optional[str] = None

    @field_validator("date_field", "closing_stock_field", "opening_stock_field", "sales_field", "receipt_field", "other_inbound_field", "other_outbound_field")
    @classmethod
    def validate_identifier(cls, value):
        if value is not None and not IDENTIFIER.match(value):
            raise ValueError("字段名只能包含字母、数字和下划线")
        return value


class InventoryCopilotRequest(BaseModel):
    data_source_id: int
    table_name: str
    start_date: str
    end_date: str
    dimensions: list[str] = Field(..., min_length=1, max_length=10)
    entity_keys: list[str] = Field(..., min_length=1, max_length=20)
    fields: InventoryFieldConfig
    filters: dict[str, Any] = Field(default_factory=dict)
    stockout_cover_days: float = Field(7, ge=0, le=365)
    overstock_cover_days: float = Field(60, ge=1, le=3650)
    include_ai_summary: bool = True
    limit: int = Field(500, ge=1, le=1000)

    @field_validator("table_name")
    @classmethod
    def validate_table_name(cls, value):
        if not QUALIFIED_IDENTIFIER.match(value):
            raise ValueError("表名必须是安全的一至三级限定名称")
        return value

    @field_validator("dimensions", "entity_keys")
    @classmethod
    def validate_identifiers(cls, values):
        if len(set(values)) != len(values):
            raise ValueError("维度或实体键不能重复")
        if any(not IDENTIFIER.match(value) for value in values):
            raise ValueError("维度和实体键只能包含字母、数字和下划线")
        return values

    @field_validator("filters")
    @classmethod
    def validate_filter_names(cls, values):
        if any(not IDENTIFIER.match(key) for key in values):
            raise ValueError("过滤字段名不安全")
        return values

    @model_validator(mode="after")
    def validate_grain(self):
        missing = [dimension for dimension in self.dimensions if dimension not in self.entity_keys]
        if missing:
            raise ValueError(f"展示维度必须包含在实体键中: {', '.join(missing)}")
        if self.start_date > self.end_date:
            raise ValueError("start_date 不能晚于 end_date")
        if self.stockout_cover_days >= self.overstock_cover_days:
            raise ValueError("缺货阈值必须小于积压阈值")
        return self
