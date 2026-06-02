# backend/app/utils/llm_client.py
"""
LLM 客户端封装
支持多种 LLM 提供商: OpenAI, Azure OpenAI, Ollama, Anthropic
"""
import logging
import os
import time
from enum import Enum
from typing import List, Dict, Any, Optional, Type
import httpx
from pydantic import BaseModel
from app.config import get_settings

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    """LLM 提供商枚举"""
    OPENAI = "openai"
    AZURE = "azure"
    OLLAMA = "ollama"
    ANTHROPIC = "anthropic"


class LLMAdapter(str, Enum):
    """LLM 调用适配器枚举"""
    RAW = "raw"
    LANGCHAIN = "langchain"


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
        self.adapter = (getattr(settings, 'llm_adapter', 'raw') or 'raw').lower()
        self.provider = (provider or settings.llm_provider or "openai").lower()
        self.max_retries = settings.nl2sql_max_retries or 2
        self.timeout = settings.nl2sql_timeout or 300
        self.api_mode = getattr(settings, 'llm_api_mode', 'chat') or 'chat'

        logger.info(
            "LLM Client initialized | adapter=%s provider=%s model=%s api_base=%s mode=%s timeout=%ds",
            self.adapter, self.provider, settings.llm_model or 'default',
            settings.llm_api_base or 'default', self.api_mode, self.timeout,
        )

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

        logger.info("LLM.chat() called | provider=%s temperature=%s messages=%d",
                     self.provider, temperature, len(messages))

        # 消息摘要日志（DEBUG 级别）
        if logger.isEnabledFor(logging.DEBUG):
            for i, msg in enumerate(messages):
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                logger.debug("  Message[%d] role=%s content_len=%d", i, role, len(content))
                if i == 0:
                    logger.debug("    (system prompt length: %d chars)", len(content))
                else:
                    logger.debug("    %s", content[:150] if len(content) > 150 else content)

        logger.info("Sending request to LLM...")

        if self.adapter == LLMAdapter.LANGCHAIN:
            result = self._call_langchain(messages, temperature)
        elif self.adapter != LLMAdapter.RAW:
            raise LLMError(f"Unsupported LLM adapter: {self.adapter}", self.provider)
        elif self.provider == LLMProvider.OPENAI:
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
        logger.info("LLM.chat() completed | elapsed=%.2fms response_len=%d preview=%s",
                     elapsed, len(result), result_preview)
        return result

    @property
    def supports_structured_output(self) -> bool:
        """当前配置是否支持结构化输出"""
        if not self.settings.nl2sql_structured_output_enabled:
            return False
        return (
            self.adapter == LLMAdapter.LANGCHAIN
            and self.provider == LLMProvider.OPENAI
            and self.api_mode in {"chat", "responses"}
        )

    def chat_structured(
        self,
        messages: List[Dict[str, str]],
        response_model: Type[BaseModel],
        temperature: float = 0.0
    ) -> Dict[str, Any]:
        """
        调用 LLM 并按 Pydantic schema 返回结构化结果。

        当前仅 LangChain OpenAI-compatible chat/responses 模式支持。业务层应在失败时回退到 chat()。
        """
        if not self.supports_structured_output:
            raise LLMError(
                f"Structured output is not supported by adapter={self.adapter}, "
                f"provider={self.provider}, api_mode={self.api_mode}",
                self.provider
            )

        result = self._call_langchain_structured(messages, response_model, temperature)
        if isinstance(result, BaseModel):
            return result.model_dump()
        if isinstance(result, dict):
            return result
        if hasattr(result, "model_dump"):
            return result.model_dump()
        raise LLMError(
            f"LangChain structured output returned unsupported type: {type(result).__name__}",
            self.provider
        )

    def _call_langchain(self, messages: List[Dict[str, str]], temperature: float) -> str:
        """使用 LangChain 调用 OpenAI 兼容 Chat 模型"""
        lc_messages = self._build_langchain_messages(messages)
        model = self._build_langchain_chat_model(temperature)

        logger.info(
            "LangChain call | model=%s base_url=%s timeout=%ds temperature=%s messages=%d retries=%d",
            self.settings.llm_model or 'gpt-3.5-turbo', self.settings.llm_api_base,
            self.timeout, temperature, len(lc_messages), self.max_retries,
        )

        for attempt in range(self.max_retries + 1):
            try:
                request_start = time.time()
                response = model.invoke(lc_messages)
                request_elapsed = (time.time() - request_start) * 1000

                content = self._extract_langchain_content(response)
                token_info = ""
                if hasattr(response, "response_metadata") and response.response_metadata:
                    meta = response.response_metadata
                    if "token_usage" in meta:
                        token_info = f", token_usage={meta['token_usage']}"
                    elif "usage" in meta:
                        token_info = f", usage={meta['usage']}"

                logger.info("LangChain call succeeded | elapsed=%.2fms%s response_len=%d",
                             request_elapsed, token_info, len(content))
                return content

            except Exception as e:
                logger.warning("LangChain attempt %d/%d failed: %s: %s",
                               attempt + 1, self.max_retries + 1, type(e).__name__, e)
                if attempt >= self.max_retries:
                    logger.error("LangChain max retries reached, giving up")
                    raise LLMError(f"LangChain OpenAI API error after {self.max_retries} retries: {e}", self.provider) from e
                logger.warning("Retrying... (%d/%d)", attempt + 1, self.max_retries)

    def _call_langchain_structured(
        self,
        messages: List[Dict[str, str]],
        response_model: Type[BaseModel],
        temperature: float
    ) -> Any:
        """使用 LangChain 结构化输出调用模型"""
        lc_messages = self._build_langchain_messages(messages)
        model = self._build_langchain_chat_model(temperature)

        logger.info(
            "LangChain structured call | model=%s response_model=%s messages=%d",
            self.settings.llm_model or 'gpt-3.5-turbo', response_model.__name__, len(lc_messages),
        )

        try:
            request_start = time.time()
            structured_model = model.with_structured_output(response_model)
            result = structured_model.invoke(lc_messages)
            request_elapsed = (time.time() - request_start) * 1000

            if isinstance(result, BaseModel):
                logger.info("LangChain structured succeeded | elapsed=%.2fms preview=%s",
                             request_elapsed, result.model_dump_json()[:200])
            else:
                logger.info("LangChain structured succeeded | elapsed=%.2fms", request_elapsed)
            return result
        except Exception as e:
            logger.error("LangChain structured call failed: %s: %s", type(e).__name__, e)
            raise LLMError(f"LangChain structured output error: {str(e)}", self.provider) from e

    def _build_langchain_messages(self, messages: List[Dict[str, str]]) -> List[Any]:
        """将 OpenAI 风格消息转换为 LangChain 消息对象"""
        if self.provider != LLMProvider.OPENAI:
            raise LLMError(
                f"LangChain adapter currently supports only openai provider, got: {self.provider}",
                self.provider
            )
        if self.api_mode not in {"chat", "responses"}:
            raise LLMError(
                f"LangChain adapter currently supports only chat/responses api mode, got: {self.api_mode}",
                self.provider
            )

        try:
            from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
        except ImportError as e:
            raise LLMError(
                "LangChain adapter requires langchain-core. "
                "Install backend requirements before enabling LLM_ADAPTER=langchain.",
                self.provider
            ) from e

        lc_messages = []
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            if role == "system":
                lc_messages.append(SystemMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))
            else:
                lc_messages.append(HumanMessage(content=content))
        return lc_messages

    def _build_langchain_chat_model(self, temperature: float) -> Any:
        """构建 LangChain ChatOpenAI 模型"""
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as e:
            raise LLMError(
                "LangChain adapter requires langchain-core and langchain-openai. "
                "Install backend requirements before enabling LLM_ADAPTER=langchain.",
                self.provider
            ) from e

        kwargs = {
            "model": self.settings.llm_model or "gpt-3.5-turbo",
            "api_key": self.settings.llm_api_key,
            "base_url": self.settings.llm_api_base,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "temperature": temperature,
        }
        if self.api_mode == "responses":
            kwargs["use_responses_api"] = True
            kwargs["output_version"] = "responses/v1"

        return ChatOpenAI(**kwargs)

    def _extract_langchain_content(self, response: Any) -> str:
        """提取 LangChain 响应文本"""
        content = getattr(response, "content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    parts.append(str(item.get("text") or item.get("content") or ""))
                else:
                    parts.append(str(item))
            return "".join(parts)
        return str(content)

    def _call_openai(self, messages: List[Dict[str, str]], temperature: float) -> str:
        """调用 OpenAI 兼容 API（使用原生 httpx）

        根据 api_mode 选择:
        - chat: 使用 /chat/completions 端点
        - responses: 使用 /responses 端点 (新版本 API)
        """
        import urllib3

        # 仅当 SSL 验证关闭时抑制警告
        if not self.settings.ssl_verify_enabled:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        # 根据 API 模式选择端点
        if self.api_mode == "responses":
            url = f"{self.settings.llm_api_base}/responses"
            data = {
                "model": self.settings.llm_model or "gpt-3.5-turbo",
                "input": messages
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

        logger.info("OpenAI call | mode=%s url=%s model=%s timeout=%ds ssl_verify=%s",
                     self.api_mode, url, data['model'], self.timeout, self.settings.ssl_verify_enabled)

        for attempt in range(self.max_retries + 1):
            try:
                logger.debug("OpenAI attempt %d/%d: sending request...", attempt + 1, self.max_retries + 1)
                request_start = time.time()
                response = httpx.post(
                    url,
                    json=data,
                    headers=headers,
                    timeout=self.timeout,
                    verify=self.settings.ssl_verify_enabled,
                )
                request_elapsed = (time.time() - request_start) * 1000

                logger.debug("OpenAI response | status=%d elapsed=%.2fms size=%d bytes",
                              response.status_code, request_elapsed, len(response.content))

                response.raise_for_status()
                result = response.json()

                # 根据 API 模式提取响应内容
                if self.api_mode == "responses":
                    content = ""
                    output = result.get("output", [])
                    for item in output:
                        if item.get("type") == "message":
                            for c in item.get("content", []):
                                if c.get("type") == "output_text":
                                    content = c.get("text", "")
                                    break
                    if content:
                        logger.info("OpenAI (responses) succeeded | content=%s...", content[:100])
                        return content
                    logger.error("OpenAI (responses) empty content, raw: %s", result)
                else:
                    content = result["choices"][0]["message"].get("content")
                    if content:
                        logger.info("OpenAI (chat) succeeded | content=%s...", content[:100])
                        return content
                    reasoning = result["choices"][0]["message"].get("reasoning")
                    if reasoning:
                        logger.info("OpenAI (chat) succeeded (reasoning) | content=%s...", reasoning[:100])
                        return reasoning

                logger.error("OpenAI returned empty content, raw: %s", result)
                raise ValueError("LLM 返回空内容")
            except httpx.HTTPStatusError as e:
                logger.error("OpenAI HTTP error | status=%d body=%s", e.response.status_code, e.response.text[:200])
                if attempt >= self.max_retries:
                    logger.error("OpenAI max retries reached")
                    raise LLMError(f"OpenAI API error after {self.max_retries} retries: {str(e)}", "openai", e.response.status_code)
                logger.warning("OpenAI retrying (%d/%d)...", attempt + 1, self.max_retries)
            except httpx.TimeoutException as e:
                logger.error("OpenAI timeout after %ds", self.timeout)
                if attempt >= self.max_retries:
                    logger.error("OpenAI max retries reached on timeout")
                    raise LLMError(f"OpenAI API timeout after {self.max_retries} retries: {str(e)}", "openai")
                logger.warning("OpenAI retrying on timeout (%d/%d)...", attempt + 1, self.max_retries)
            except httpx.RequestError as e:
                logger.error("OpenAI request error: %s: %s", type(e).__name__, str(e))
                if attempt >= self.max_retries:
                    logger.error("OpenAI max retries reached on request error")
                    raise LLMError(f"OpenAI API error after {self.max_retries} retries: {str(e)}", "openai")
                logger.warning("OpenAI retrying on error (%d/%d)...", attempt + 1, self.max_retries)

        return ""

    def _call_azure(self, messages: List[Dict[str, str]], temperature: float) -> str:
        """调用 Azure OpenAI API (兼容新版 OpenAI SDK v1.0+)

        如果未配置 azure_endpoint 但配置了 llm_api_base，自动回退到 OpenAI 兼容模式
        """
        if not self.settings.azure_openai_endpoint and self.settings.llm_api_base:
            logger.warning("No azure_endpoint configured, llm_api_base detected, falling back to OpenAI compatible mode")
            return self._call_openai(messages, temperature)

        try:
            from openai import AzureOpenAI
            client = AzureOpenAI(
                api_key=self.settings.llm_api_key,
                api_version="2024-02-01",
                azure_endpoint=self.settings.azure_openai_endpoint
            )
        except ImportError:
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


    def chat_stream(self, messages: List[Dict[str, str]], temperature: float = 0.0):
        """
        流式调用 LLM，逐 token 产出。

        Yields:
            str: 每个 token 的文本内容
        """
        if self.adapter in (LLMAdapter.LANGCHAIN,):
            yield from self._stream_langchain(messages, temperature)
        elif self.provider == LLMProvider.OPENAI:
            yield from self._stream_openai(messages, temperature)
        else:
            # 不支持流式的 provider 回退到完整响应
            yield self.chat(messages, temperature)

    def _stream_langchain(self, messages, temperature):
        """LangChain 流式调用"""
        lc_messages = self._build_langchain_messages(messages)
        model = self._build_langchain_chat_model(temperature)
        for chunk in model.stream(lc_messages):
            content = chunk.content if hasattr(chunk, "content") else str(chunk)
            if content:
                yield content

    def _stream_openai(self, messages, temperature):
        """OpenAI 原生 httpx 流式调用"""
        import urllib3
        if not self.settings.ssl_verify_enabled:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        url = f"{self.settings.llm_api_base}/chat/completions"
        data = {
            "model": self.settings.llm_model or "gpt-3.5-turbo",
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.settings.llm_api_key}",
        }

        try:
            with httpx.Client(timeout=self.timeout, verify=self.settings.ssl_verify_enabled) as client:
                with client.stream("POST", url, json=data, headers=headers) as resp:
                    for line in resp.iter_lines():
                        if not line or line.startswith(":") or line.startswith("data: [DONE]"):
                            continue
                        if line.startswith("data: "):
                            try:
                                chunk = json.loads(line[6:])
                                delta = chunk.get("choices", [{}])[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                            except json.JSONDecodeError:
                                continue
        except Exception as e:
            logger.error("OpenAI stream error: %s", e)
            # fallback: complete response
            yield self.chat(messages, temperature)


def get_llm_client(provider: str = None) -> LLMClient:
    """获取 LLM 客户端实例"""
    return LLMClient(provider)
