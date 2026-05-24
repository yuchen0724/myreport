"""Test structured output and full NL2SQL parse."""
import sys
sys.path.insert(0, "/home/zhou/myreport/backend")

from app.schemas.nl2sql import GeneratedSQLResult
from app.utils.llm_client import get_llm_client

# 1. 测试结构化输出
client = get_llm_client()
print("=== 1. supports_structured_output:", client.supports_structured_output)
print("=== 2. 测试 chat_structured ===")

messages = [
    {"role": "system", "content": "You are a SQL expert. Return only valid JSON."},
    {"role": "user", "content": 'Generate SQL: {"sql": "SELECT 1", "confidence": 0.9, "explanation": "test"}'}
]

try:
    result = client.chat_structured(messages, GeneratedSQLResult, temperature=0.0)
    print("结构化输出成功:", result)
except Exception as e:
    print(f"结构化输出失败 (预期fallback): {type(e).__name__}: {e}")
