# backend/tests/test_nl2sql.py
import pytest
from app.utils.nl2sql_rules import NL2SQLRuleEngine

def test_extract_table_name():
    """测试提取表名"""
    question = "从用户表中查询所有数据"
    table_name = NL2SQLRuleEngine._extract_table_name(question)
    assert table_name == "用户"

def test_extract_columns():
    """测试提取字段"""
    question = "查询用户名和年龄"
    columns = NL2SQLRuleEngine._extract_columns(question)
    assert "用户名" in columns
    assert "年龄" in columns

def test_parse_question():
    """测试解析问题"""
    question = "查询用户表中的前10条记录"
    sql, confidence = NL2SQLRuleEngine.parse_question(question)
    assert "SELECT" in sql
    assert "FROM" in sql
    assert "LIMIT" in sql
    assert confidence > 0
