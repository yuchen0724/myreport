# backend/app/utils/llm_client.py
"""
LLM 客户端封装
支持多种 LLM 提供商: OpenAI, Azure OpenAI, Ollama, Anthropic
"""
import json
import time
import logging
import re
from enum import Enum
from typing import List, Dict, Any, Optional, Type, Union, AsyncGenerator, Callable
import httpx
from pydantic import BaseModel, Field
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


class ToolDefinition(BaseModel):
    """函数调用工具定义"""
    name: str = Field(..., description="工具名称")
    description: str = Field("", description="工具描述")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="JSON Schema 参数定义")


class ToolCallResult(BaseModel):
    """工具调用结果（OpenAI 格式）"""
    id: str = Field(default="", description="工具调用 ID")
    name: str = Field(..., description="工具名称")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="工具参数")


class ToolChoice(BaseModel):
    """工具选择结果"""
    tool_calls: Optional[List[ToolCallResult]] = Field(None, description="工具调用列表")
    content: Optional[str] = Field(None, description="文本回复内容")


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
        self._proxy_client = None  # lazy init

        logger.info(
            "LLM Client initialized | adapter=%s provider=%s model=%s api_base=%s mode=%s timeout=%ds",
            self.adapter, self.provider, settings.llm_model or 'default',
            settings.llm_api_base or 'default', self.api_mode, self.timeout,
        )

    def _get_httpx_client(self) -> Optional[Any]:
        """创建带代理的 httpx 客户端（如需），供 LangChain / raw OpenAI 使用"""
        if self._proxy_client is not None:
            return self._proxy_client
        if not getattr(self.settings, "llm_use_proxy", False) or not getattr(self.settings, "llm_proxy_host", ""):
            self._proxy_client = None
            return None
        proxy_type = getattr(self.settings, "llm_proxy_type", "http").lower()
        proxy_host = self.settings.llm_proxy_host
        proxy_port = getattr(self.settings, "llm_proxy_port", 0)
        proxy_user = getattr(self.settings, "llm_proxy_username", "") or ""
        proxy_pass = getattr(self.settings, "llm_proxy_password", "") or ""

        auth_part = f"{proxy_user}:{proxy_pass}@" if proxy_user else ""
        if proxy_type in ("http", "https"):
            proxy_url = f"{proxy_type}://{auth_part}{proxy_host}:{proxy_port}"
            self._proxy_client = httpx.Client(
                proxies={"http://": proxy_url, "https://": proxy_url},
                timeout=self.timeout,
            )
            logger.info(f"[LLM] 使用 HTTP 代理: {proxy_host}:{proxy_port}")
        elif proxy_type == "socks5":
            proxy_url = f"socks5://{auth_part}{proxy_host}:{proxy_port}"
            try:
                from httpx import Proxy
                proxy_obj = Proxy(url=proxy_url)
                transport = httpx.HTTPTransport(proxy=proxy_obj)
                self._proxy_client = httpx.Client(transport=transport, timeout=self.timeout)
                logger.info(f"[LLM] 使用 SOCKS5 代理: {proxy_host}:{proxy_port}")
            except ImportError:
                logger.warning("[LLM] SOCKS5 代理需要安装 socksio: pip install httpx[socks]")
                self._proxy_client = None
            except Exception as e:
                logger.warning(f"[LLM] SOCKS5 代理创建失败，回退直连: {e}")
                self._proxy_client = None
        else:
            logger.warning(f"[LLM] 不支持的代理类型: {proxy_type}，回退直连")
            self._proxy_client = None
        return self._proxy_client

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

    @property
    def supports_tools(self) -> bool:
        """当前配置是否支持原生函数调用"""
        return (
            self.provider == LLMProvider.OPENAI
            and self.api_mode == "chat"
        )

    def chat_with_tools(
        self,
        messages: List[Dict[str, str]],
        tools: List[ToolDefinition],
        temperature: float = 0.0,
        tool_choice: Optional[Union[str, Dict]] = None,
    ) -> ToolChoice:
        """
        原生函数调用（OpenAI工具调用模式）。

        Args:
            messages: 消息列表
            tools: 工具定义列表
            temperature: 温度参数
            tool_choice: 工具选择策略，"auto"/"none"/{"type":"function","function":{"name":"xxx"}}

        Returns:
            ToolChoice: 包含工具调用或文本回复
        """
        start_time = time.time()

        if not self.supports_tools:
            logger.warning("Native tools not supported, falling back to chat")
            content = self.chat(messages, temperature)
            return ToolChoice(content=content)

        logger.info("LLM.chat_with_tools() | provider=%s tools=%d messages=%d",
                     self.provider, len(tools), len(messages))

        url = f"{self.settings.llm_api_base}/chat/completions"
        data = {
            "model": self.settings.llm_model or "gpt-4o-mini",
            "messages": messages,
            "temperature": temperature,
            "tools": [self._tool_to_openai(t) for t in tools],
        }
        if tool_choice:
            data["tool_choice"] = tool_choice

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.settings.llm_api_key}"
        }

        for attempt in range(self.max_retries + 1):
            try:
                response = httpx.post(
                    url, json=data, headers=headers,
                    timeout=self.timeout, verify=self.settings.ssl_verify_enabled,
                )
                response.raise_for_status()
                result = response.json()
                msg = result["choices"][0]["message"]

                tool_calls = msg.get("tool_calls")
                if tool_calls:
                    parsed_calls = []
                    for tc in tool_calls:
                        try:
                            args = json.loads(tc["function"]["arguments"])
                        except (json.JSONDecodeError, KeyError):
                            args = {}
                        parsed_calls.append(ToolCallResult(
                            id=tc.get("id", ""),
                            name=tc["function"]["name"],
                            arguments=args,
                        ))
                    elapsed = (time.time() - start_time) * 1000
                    logger.info("chat_with_tools completed | elapsed=%.2fms tool_calls=%d",
                                 elapsed, len(parsed_calls))
                    return ToolChoice(tool_calls=parsed_calls)

                content = msg.get("content", "")
                elapsed = (time.time() - start_time) * 1000
                logger.info("chat_with_tools completed | elapsed=%.2fms text_reply", elapsed)
                return ToolChoice(content=content)

            except Exception as e:
                logger.warning("chat_with_tools attempt %d/%d failed: %s",
                               attempt + 1, self.max_retries + 1, e)
                if attempt >= self.max_retries:
                    logger.error("chat_with_tools max retries reached, falling back to chat")
                    content = self.chat(messages, temperature)
                    return ToolChoice(content=content)

        return ToolChoice(content="")

    def _tool_to_openai(self, tool: ToolDefinition) -> Dict:
        """将 ToolDefinition 转为 OpenAI tools 格式"""
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            }
        }

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

    def get_embedding(self, text: str, model: str = None) -> List[float]:
        """
        获取文本嵌入向量（用于语义缓存和相似度匹配）

        Args:
            text: 输入文本
            model: embedding 模型名

        Returns:
            嵌入向量
        """
        url = f"{self.settings.llm_api_base}/embeddings"
        data = {
            "model": model or self.settings.llm_embedding_model or "text-embedding-3-small",
            "input": text,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.settings.llm_api_key}"
        }
        try:
            client = self._get_httpx_client()
            if client is not None:
                resp = client.post(url, json=data, headers=headers)
            else:
                resp = httpx.post(url, json=data, headers=headers, timeout=30,
                                  verify=self.settings.ssl_verify_enabled)
            resp.raise_for_status()
            result = resp.json()
            return result["data"][0]["embedding"]
        except Exception as e:
            logger.warning(f"get_embedding failed: {e}")
            return []

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
            from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
        except ImportError as exc:
            raise LLMError(
                "LangChain adapter requires langchain-core and langchain-openai",
                self.provider,
            ) from exc
        lc_messages = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "system":
                lc_messages.append(SystemMessage(content=content))
            elif role == "user":
                lc_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))
            else:
                lc_messages.append(HumanMessage(content=content))
        return lc_messages

    def _build_langchain_chat_model(self, temperature: float) -> Any:
        """构造 LangChain ChatOpenAI 模型（支持代理）"""
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:
            raise LLMError(
                "LangChain adapter requires langchain-core and langchain-openai",
                self.provider,
            ) from exc

        kwargs = dict(
            model=self.settings.llm_model or "gpt-3.5-turbo",
            temperature=temperature,
            api_key=self.settings.llm_api_key,
            base_url=self.settings.llm_api_base,
            timeout=self.timeout,
            max_retries=self.max_retries,
            use_responses_api=self.api_mode == "responses",
        )
        if self.api_mode == "responses":
            kwargs["output_version"] = "responses/v1"
        proxy_client = self._get_httpx_client()
        if proxy_client is not None:
            kwargs["http_client"] = proxy_client
        return ChatOpenAI(**kwargs)

    def _extract_langchain_content(self, response: Any) -> str:
        """从 LangChain 响应中提取文本内容"""
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

                proxy_client = self._get_httpx_client()
                if proxy_client is not None:
                    response = proxy_client.post(url, json=data, headers=headers)
                else:
                    response = httpx.post(
                        url, json=data, headers=headers,
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
        """调用 Ollama API"""
        ollama_base = self.settings.ollama_base_url or "http://localhost:11434"
        url = f"{ollama_base}/api/chat"
        data = {
            "model": self.settings.ollama_model or "qwen2.5-coder:7b",
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature}
        }
        headers = {"Content-Type": "application/json"}
        if self.settings.ollama_api_key:
            headers["Authorization"] = f"Bearer {self.settings.ollama_api_key}"

        for attempt in range(self.max_retries + 1):
            try:
                response = httpx.post(url, json=data, headers=headers, timeout=self.timeout)
                response.raise_for_status()
                result = response.json()
                return result.get("message", {}).get("content", "")
            except Exception as e:
                if attempt >= self.max_retries:
                    raise LLMError(f"Ollama API error after {self.max_retries} retries: {str(e)}", "ollama")

        return ""

    def _call_anthropic(self, messages: List[Dict[str, str]], temperature: float) -> str:
        """调用 Anthropic Claude API"""
        from anthropic import Anthropic
        client = Anthropic(api_key=self.settings.anthropic_api_key)

        # 提取 system 消息
        system_content = None
        api_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_content = msg["content"]
            else:
                api_messages.append({"role": msg["role"], "content": msg["content"]})

        for attempt in range(self.max_retries + 1):
            try:
                kwargs = {
                    "model": self.settings.anthropic_model or "claude-3-5-sonnet-20241022",
                    "max_tokens": 4096,
                    "messages": api_messages,
                    "temperature": temperature,
                }
                if system_content:
                    kwargs["system"] = system_content

                response = client.messages.create(**kwargs)
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

    def chat_stream_with_tools(
        self,
        messages: List[Dict[str, str]],
        tools: List[ToolDefinition],
        temperature: float = 0.0,
    ):
        """
        流式调用 LLM 并检测工具调用（OpenAI 原生流式工具调用模式）。

        Yields dict:
            {"type": "text", "content": str} — 文本 token
            {"type": "tool_call", "tool_name": str, "arguments": dict} — 完整工具调用
        """
        if not self.supports_tools:
            # 回退到普通流式 + JSON 解析
            yield from self._stream_tools_via_text(messages, tools, temperature)
            return

        url = f"{self.settings.llm_api_base}/chat/completions"
        data = {
            "model": self.settings.llm_model or "gpt-4o-mini",
            "messages": messages,
            "temperature": temperature,
            "stream": True,
            "tools": [self._tool_to_openai(t) for t in tools],
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.settings.llm_api_key}",
        }

        try:
            tool_calls_buffer = {}  # index -> {name, arguments_chunks}
            text_buffer = []

            proxy_client = self._get_httpx_client()
            if proxy_client is not None:
                with proxy_client.stream("POST", url, json=data, headers=headers) as resp:
                    for line in resp.iter_lines():
                        if not line or line.startswith(":") or line.startswith("data: [DONE]"):
                            continue
                        if line.startswith("data: "):
                            try:
                                chunk = json.loads(line[6:])
                                delta = chunk.get("choices", [{}])[0].get("delta", {})

                                # 文本 delta
                                content = delta.get("content", "")
                                if content:
                                    text_buffer.append(content)
                                    yield {"type": "text", "content": content}

                                # 工具调用 delta
                                tc_list = delta.get("tool_calls", [])
                                for tc in tc_list:
                                    idx = tc.get("index", 0)
                                    if idx not in tool_calls_buffer:
                                        tool_calls_buffer[idx] = {
                                            "id": tc.get("id", ""),
                                            "name": tc["function"].get("name", "") if tc.get("function") else "",
                                            "arguments_chunks": [],
                                        }
                                    if tc.get("function", {}).get("arguments"):
                                        tool_calls_buffer[idx]["arguments_chunks"].append(
                                            tc["function"]["arguments"]
                                        )
                                    if tc.get("id"):
                                        tool_calls_buffer[idx]["id"] = tc["id"]
                                    if tc.get("function", {}).get("name"):
                                        tool_calls_buffer[idx]["name"] = tc["function"]["name"]

                            except json.JSONDecodeError:
                                continue
            else:
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
                                        text_buffer.append(content)
                                        yield {"type": "text", "content": content}

                                    tc_list = delta.get("tool_calls", [])
                                    for tc in tc_list:
                                        idx = tc.get("index", 0)
                                        if idx not in tool_calls_buffer:
                                            tool_calls_buffer[idx] = {
                                                "id": tc.get("id", ""),
                                                "name": tc["function"].get("name", "") if tc.get("function") else "",
                                                "arguments_chunks": [],
                                            }
                                        if tc.get("function", {}).get("arguments"):
                                            tool_calls_buffer[idx]["arguments_chunks"].append(
                                                tc["function"]["arguments"]
                                            )
                                        if tc.get("id"):
                                            tool_calls_buffer[idx]["id"] = tc["id"]
                                        if tc.get("function", {}).get("name"):
                                            tool_calls_buffer[idx]["name"] = tc["function"]["name"]

                                except json.JSONDecodeError:
                                    continue

            # 完成时，合并工具调用
            if tool_calls_buffer:
                for idx in sorted(tool_calls_buffer.keys()):
                    buf = tool_calls_buffer[idx]
                    full_args = "".join(buf["arguments_chunks"])
                    try:
                        parsed_args = json.loads(full_args) if full_args else {}
                    except json.JSONDecodeError:
                        parsed_args = {"_raw": full_args}
                    yield {
                        "type": "tool_call",
                        "tool_name": buf["name"],
                        "arguments": parsed_args,
                        "id": buf["id"],
                    }
            elif text_buffer:
                # 纯文本回复，无需额外操作
                pass

        except Exception as e:
            logger.warning(f"chat_stream_with_tools failed: {e}, falling back")
            yield from self._stream_tools_via_text(messages, tools, temperature)

    def _stream_tools_via_text(self, messages, tools, temperature):
        """回退方案：普通流式 + 从文本解析工具调用"""
        # 收集完整文本
        full_text = []
        for token in self.chat_stream(messages, temperature):
            full_text.append(token)
            yield {"type": "text", "content": token}

        complete = "".join(full_text)
        # 尝试解析 JSON 工具调用
        json_match = re.search(r'\{"tool"\s*:\s*"[^"]+"', complete)
        if json_match:
            # 让调用方自行解析
            pass

    def _stream_langchain(self, messages, temperature):
        """LangChain 流式调用（兼容多种模型响应格式）"""
        lc_messages = self._build_langchain_messages(messages)
        model = self._build_langchain_chat_model(temperature)
        for chunk in model.stream(lc_messages):
            raw = chunk.content if hasattr(chunk, "content") else chunk
            # 兼容不同模型返回格式：str / list[dict] / list[str]
            if isinstance(raw, str):
                if raw:
                    yield raw
            elif isinstance(raw, list):
                for item in raw:
                    if isinstance(item, str):
                        if item:
                            yield item
                    elif isinstance(item, dict):
                        text = item.get("text") or item.get("content") or ""
                        if text:
                            yield text
            elif raw:
                yield str(raw)

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
            proxy_client = self._get_httpx_client()
            if proxy_client is not None:
                with proxy_client.stream("POST", url, json=data, headers=headers) as resp:
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
            else:
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
            logger.error(f"Stream OpenAI error: {e}")
            raise

    def _summarize_messages(self, messages: List[Dict[str, str]], max_tokens: int = 300) -> str:
        """
        用 LLM 对对话消息做语义摘要。

        Args:
            messages: 需要摘要的消息列表
            max_tokens: 摘要最大 token 数

        Returns:
            摘要文本
        """
        if not messages:
            return ""

        # 提取关键的 SQL、指标、结论
        summary_prompt = f"""请用中文简要总结以下对话的核心内容（{max_tokens} token以内），包括：
1. 用户关注的数据指标和维度
2. 执行过的SQL查询（简要描述）
3. 发现的关键结论

对话内容：
{json.dumps([{"role": m["role"], "content": m["content"][:300]} for m in messages], ensure_ascii=False, default=str)[:3000]}"""
        try:
            return self.chat([
                {"role": "system", "content": "你是一个专业的对话摘要助手，请简洁准确地总结对话。"},
                {"role": "user", "content": summary_prompt},
            ], temperature=0.0)
        except Exception as e:
            logger.warning(f"对话摘要失败: {e}")
            return f"[历史摘要: 共 {len(messages)//2} 轮对话]"


def get_llm_client(provider: str = None) -> LLMClient:
    """获取 LLM 客户端实例的工厂函数（保持与已有代码的兼容性）"""
    return LLMClient(provider)
