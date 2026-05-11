# backend/app/utils/llm_client.py
"""
LLM 客户端封装
支持多种 LLM 提供商: OpenAI, Azure OpenAI, Ollama, Anthropic
"""
import json
import logging
import os
import time
from enum import Enum
from typing import List, Dict, Any, Optional
import httpx
from app.config import get_settings

# 同时使用 logger 和 print，确保日志输出可见
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # 设置为 DEBUG 级别

def log_print(*args, **kwargs):
    """同时输出到 logger 和 stdout"""
    msg = " ".join(str(a) for a in args)
    print(f"[LLM] {msg}", flush=True)
    logger.info(msg)

class LLMProvider(str, Enum):
    """LLM 提供商枚举"""
    OPENAI = "openai"
    AZURE = "azure"
    OLLAMA = "ollama"
    ANTHROPIC = "anthropic"


class LLMError(Exception):
    """LLM 调用错误"""
    def __init__(self, message: str, provider: str = None, status_code: int = None):
        self.message = message
        self.provider = provider
        self.status_code = status_code
        super().__init__(self.message)


class LLMClient:
    """LLM 客户端封装类"""
    
    def __init__(self, provider: str = None):
        settings = get_settings()
        self.settings = settings
        self.provider = (provider or settings.llm_provider or "openai").lower()
        self.max_retries = settings.nl2sql_max_retries or 2
        self.timeout = settings.nl2sql_timeout or 300  # 从配置读取超时时间
        self.api_mode = getattr(settings, 'llm_api_mode', 'chat') or 'chat'  # chat 或 responses
        
        print(f"[LLM] ═════════ 初始化 LLM Client ═════════", flush=True)
        print(f"[LLM] ├─ Provider: {self.provider}", flush=True)
        print(f"[LLM] ├─ Model: {settings.llm_model or 'default'}", flush=True)
        print(f"[LLM] ├─ API Base: {settings.llm_api_base or 'default'}", flush=True)
        print(f"[LLM] ├─ API Mode: {self.api_mode}", flush=True)
        print(f"[LLM] ├─ Timeout: {self.timeout}s", flush=True)
        print(f"[LLM] ├��� Max Retries: {self.max_retries}", flush=True)
        print(f"[LLM] └─ API Key: {settings.llm_api_key[:10] if settings.llm_api_key else 'None'}...", flush=True)
        
    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.0) -> str:
        """
        调用 LLM 生成响应
        
        Args:
            messages: 消息列表 [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
            temperature: 温度参数，控制随机性
            
        Returns:
            模型响应文本
        """
        start_time = time.time()
        
        print(f"[LLM] ════════════ LLM.chat() 被调用 ════════════", flush=True)
        print(f"[LLM] ├─ Provider: {self.provider}", flush=True)
        print(f"[LLM] ├─ Temperature: {temperature}", flush=True)
        print(f"[LLM] ├─ Messages 数量: {len(messages)}", flush=True)
        
        # 打印消息摘要
        for i, msg in enumerate(messages):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            content_preview = content[:100] + "..." if len(content) > 100 else content
            print(f"[LLM] │   └─ Message[{i}] role={role}, content_len={len(content)}", flush=True)
            if i == 0:  # system 消息只打印长度
                print(f"[LLM] │           └─ (system prompt 长度: {len(content)} 字符)", flush=True)
            else:
                print(f"[LLM] │           └─ {content_preview}", flush=True)
        
        print(f"[LLM] └─ 开始调用 LLM...", flush=True)
        
        if self.provider == LLMProvider.OPENAI:
            result = self._call_openai(messages, temperature)
        elif self.provider == LLMProvider.AZURE:
            result = self._call_azure(messages, temperature)
        elif self.provider == LLMProvider.OLLAMA:
            result = self._call_ollama(messages, temperature)
        elif self.provider == LLMProvider.ANTHROPIC:
            result = self._call_anthropic(messages, temperature)
        else:
            raise LLMError(f"Unsupported provider: {self.provider}")
        
        elapsed = (time.time() - start_time) * 1000
        result_preview = result[:150] + "..." if len(result) > 150 else result
        print(f"[LLM] ════════════ LLM.chat() 完成 ════════════", flush=True)
        print(f"[LLM] ├─ 耗时: {elapsed:.2f}ms", flush=True)
        print(f"[LLM] ├─ 响应长度: {len(result)} 字符", flush=True)
        print(f"[LLM] └─ 响应内容: {result_preview}", flush=True)
        
        return result
    
    def _call_openai(self, messages: List[Dict[str, str]], temperature: float) -> str:
        """调用 OpenAI 兼容 API（使用原生 httpx）
        
        根据 api_mode 选择:
        - chat: 使用 /chat/completions 端点
        - responses: 使用 /responses 端点 (新版本 API)
        """
        import httpx
        import urllib3
        
        # 禁用 SSL 警告
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # 根据 API 模式选择端点
        if self.api_mode == "responses":
            url = f"{self.settings.llm_api_base}/responses"
            # Responses API 格式：将 messages 转为 input
            data = {
                "model": self.settings.llm_model or "gpt-3.5-turbo",
                "input": messages,
                "temperature": temperature
            }
        else:
            url = f"{self.settings.llm_api_base}/chat/completions"
            data = {
                "model": self.settings.llm_model or "gpt-3.5-turbo",
                "messages": messages,
                "temperature": temperature
            }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.settings.llm_api_key}"
        }
        
        logger.info("[LLM:OpenAI] ═══════════════════════════════")
        logger.info(f"[LLM:OpenAI] ├─ API Mode: {self.api_mode}")
        logger.info(f"[LLM:OpenAI] ├─ 请求URL: {url}")
        logger.info(f"[LLM:OpenAI] ├─ Model: {data['model']}")
        logger.info(f"[LLM:OpenAI] ├─ Timeout: {self.timeout}s")
        logger.info(f"[LLM:OpenAI] ├─ SSL Verify: False")
        logger.info(f"[LLM:OpenAI] ├─ Max Retries: {self.max_retries}")
        logger.info(f"[LLM:OpenAI] └─ 准备发送请求...")
        
        for attempt in range(self.max_retries + 1):
            try:
                logger.info(f"[LLM:OpenAI] ├─ Attempt {attempt + 1}/{self.max_retries + 1}: 发送请求...")
                request_start = time.time()
                response = httpx.post(
                    url, 
                    json=data, 
                    headers=headers, 
                    timeout=self.timeout,
                    verify=False  # 禁用 SSL 验证
                )
                request_elapsed = (time.time() - request_start) * 1000
                
                logger.info(f"[LLM:OpenAI] │   ├─ HTTP Status: {response.status_code}")
                logger.info(f"[LLM:OpenAI] │   ├─ 响应耗时: {request_elapsed:.2f}ms")
                logger.info(f"[LLM:OpenAI] │   ├─ 响应大小: {len(response.content)} bytes")
                
                response.raise_for_status()
                result = response.json()
                
                logger.info(f"[LLM:OpenAI] │   └─ 响应解析成功")
                
                # 根据 API 模式提取响应内容
                if self.api_mode == "responses":
                    # Responses API 格式: {"output": [{"content": [{"text": "..."}]}]}
                    content = ""
                    output = result.get("output", [])
                    for item in output:
                        if item.get("type") == "message":
                            for c in item.get("content", []):
                                if c.get("type") == "output_text":
                                    content = c.get("text", "")
                                    break
                    if content:
                        logger.info(f"[LLM:OpenAI] ✅ (Responses模式) 成功获取 content: {content[:100]}...")
                        return content
                    logger.error(f"[LLM:OpenAI] ❌ Responses 模式解析失败，原始响应: {result}")
                else:
                    # Chat Completions API 格式: {"choices": [{"message": {"content": "..."}}]}
                    content = result["choices"][0]["message"].get("content")
                    if content:
                        logger.info(f"[LLM:OpenAI] ✅ 成功获取 content: {content[:100]}...")
                        return content
                    # GLM 模型可能返回 reasoning
                    reasoning = result["choices"][0]["message"].get("reasoning")
                    if reasoning:
                        logger.info(f"[LLM:OpenAI] ✅ 成功获取 reasoning: {reasoning[:100]}...")
                        return reasoning
                
                logger.error(f"[LLM:OpenAI] ❌ LLM 返回空内容，原始响应: {result}")
                raise ValueError("LLM 返回空内容")
            except httpx.HTTPStatusError as e:
                logger.error(f"[LLM:OpenAI] ═══════════════════════════════")
                logger.error(f"[LLM:OpenAI] ├─ HTTP 错误: {e.response.status_code}")
                logger.error(f"[LLM:OpenAI] ├─ 错误响应: {e.response.text[:200]}")
                if attempt >= self.max_retries:
                    logger.error(f"[LLM:OpenAI] └─ 达到最大重试次数，放弃")
                    raise LLMError(f"OpenAI API error after {self.max_retries} retries: {str(e)}", "openai", e.response.status_code)
                logger.warning(f"[LLM:OpenAI] ├─ 重试... ({attempt + 1}/{self.max_retries})")
            except httpx.TimeoutException as e:
                logger.error(f"[LLM:OpenAI] ═══════════════════════════════")
                logger.error(f"[LLM:OpenAI] ├─ 请求超时: {self.timeout}s")
                if attempt >= self.max_retries:
                    logger.error(f"[LLM:OpenAI] └─ 达到最大重试次数，放弃")
                    raise LLMError(f"OpenAI API timeout after {self.max_retries} retries: {str(e)}", "openai")
                logger.warning(f"[LLM:OpenAI] ├─ 重试... ({attempt + 1}/{self.max_retries})")
            except httpx.RequestError as e:
                logger.error(f"[LLM:OpenAI] ═══════════════════════════════")
                logger.error(f"[LLM:OpenAI] ├─ 请求错误: {type(e).__name__}: {str(e)}")
                if attempt >= self.max_retries:
                    logger.error(f"[LLM:OpenAI] └─ 达到最大重试次数，放弃")
                    raise LLMError(f"OpenAI API error after {self.max_retries} retries: {str(e)}", "openai")
                logger.warning(f"[LLM:OpenAI] ├─ 重试... ({attempt + 1}/{self.max_retries})")
        
        return ""
    
    def _call_azure(self, messages: List[Dict[str, str]], temperature: float) -> str:
        """调用 Azure OpenAI API (兼容新版 OpenAI SDK v1.0+)
        
        如果未配置 azure_endpoint 但配置了 llm_api_base，自动回退到 OpenAI 兼容模式
        """
        # 检查是否配置了 Azure 端点，如果没有但配置了 API_BASE，回退到 OpenAI 模式
        if not self.settings.azure_openai_endpoint and self.settings.llm_api_base:
            print(f"[LLM:Azure] ⚠️ 未配置 azure_endpoint，检测到 llm_api_base，回退到 OpenAI 兼容模式", flush=True)
            return self._call_openai(messages, temperature)
        
        try:
            # 尝试使用 AzureOpenAI 客户端（新版本 SDK）
            from openai import AzureOpenAI
            client = AzureOpenAI(
                api_key=self.settings.llm_api_key,
                api_version="2024-02-01",
                azure_endpoint=self.settings.azure_openai_endpoint
            )
        except ImportError:
            # 回退到旧版方式
            from openai import OpenAI
            client = OpenAI(
                api_key=self.settings.llm_api_key,
                azure_deployment=self.settings.azure_openai_deployment or "gpt-35-turbo",
                api_version="2024-02-01",
                azure_endpoint=self.settings.azure_openai_endpoint
            )
        
        for attempt in range(self.max_retries + 1):
            try:
                response = client.chat.completions.create(
                    model=self.settings.azure_openai_deployment or "gpt-35-turbo",
                    messages=messages,
                    temperature=temperature,
                    timeout=self.timeout
                )
                return response.choices[0].message.content
            except Exception as e:
                if attempt >= self.max_retries:
                    raise LLMError(f"Azure OpenAI API error after {self.max_retries} retries: {str(e)}", "azure")
        
        return ""
    
    def _call_ollama(self, messages: List[Dict[str, str]], temperature: float) -> str:
        """调用 Ollama 本地模型"""
        base_url = self.settings.ollama_base_url or "http://localhost:11434"
        
        for attempt in range(self.max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(
                        f"{base_url}/api/chat",
                        json={
                            "model": self.settings.llm_model or "llama2",
                            "messages": messages,
                            "temperature": temperature
                        }
                    )
                    if response.status_code != 200:
                        raise LLMError(f"Ollama API error: {response.text}", "ollama", response.status_code)
                    
                    result = response.json()
                    return result.get("message", {}).get("content", "")
            except httpx.TimeoutException:
                if attempt >= self.max_retries:
                    raise LLMError(f"Ollama timeout after {self.max_retries} retries", "ollama")
            except Exception as e:
                if attempt >= self.max_retries:
                    raise LLMError(f"Ollama API error after {self.max_retries} retries: {str(e)}", "ollama")
        
        return ""
    
    def _call_anthropic(self, messages: List[Dict[str, str]], temperature: float) -> str:
        """调用 Anthropic API"""
        import anthropic
        
        client = anthropic.Anthropic(
            api_key=self.settings.llm_api_key
        )
        
        # 将消息格式转换为 Anthropic 格式
        system_message = ""
        anthropic_messages = []
        for msg in messages:
            if msg.get("role") == "system":
                system_message = msg.get("content", "")
            else:
                anthropic_messages.append(msg)
        
        for attempt in range(self.max_retries + 1):
            try:
                response = client.messages.create(
                    model=self.settings.llm_model or "claude-3-haiku-20240307",
                    max_tokens=4096,
                    system=system_message,
                    messages=anthropic_messages,
                    temperature=temperature
                )
                return response.content[0].text
            except Exception as e:
                if attempt >= self.max_retries:
                    raise LLMError(f"Anthropic API error after {self.max_retries} retries: {str(e)}", "anthropic")
        
        return ""


def get_llm_client(provider: str = None) -> LLMClient:
    """获取 LLM 客户端实例"""
    return LLMClient(provider)