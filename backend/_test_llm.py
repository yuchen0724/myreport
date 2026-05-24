"""Quick test for LLM client call."""
import sys
sys.path.insert(0, "/home/zhou/myreport/backend")
from app.utils.llm_client import get_llm_client

client = get_llm_client()
result = client.chat([{"role": "user", "content": "say hello in one word"}])
print("✅ LLM 调用成功")
print("响应:", result)
