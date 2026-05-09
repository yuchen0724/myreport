# backend/app/utils/llm_client.py
"""
LLM 客户端封装
支持多种 LLM 提供商: OpenAI, Azure OpenAI, Ollama, Anthropic
"""
import json
from enum import Enum
from typing import List, Dict, Any, Optional
import httpx
from app.config import get_settings


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
        self.max_retries = 2
        self.timeout = 30
        
    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.0) -> str:
        """
        调用 LLM 生成响应
        
        Args:
            messages: 消息列表 [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
            temperature: 温度参数，控制随机性
            
        Returns:
            模型响应文本
        """
        if self.provider == LLMProvider.OPENAI:
            return self._call_openai(messages, temperature)
        elif self.provider == LLMProvider.AZURE:
            return self._call_azure(messages, temperature)
        elif self.provider == LLMProvider.OLLAMA:
            return self._call_ollama(messages, temperature)
        elif self.provider == LLMProvider.ANTHROPIC:
            return self._call_anthropic(messages, temperature)
        else:
            raise LLMError(f"Unsupported provider: {self.provider}")
    
    def _call_openai(self, messages: List[Dict[str, str]], temperature: float) -> str:
        """调用 OpenAI API"""
        from openai import OpenAI
        
        client = OpenAI(
            api_key=self.settings.llm_api_key,
            base_url=self.settings.llm_api_base or "https://api.openai.com/v1"
        )
        
        for attempt in range(self.max_retries + 1):
            try:
                response = client.chat.completions.create(
                    model=self.settings.llm_model or "gpt-3.5-turbo",
                    messages=messages,
                    temperature=temperature,
                    timeout=self.timeout
                )
                return response.choices[0].message.content
            except Exception as e:
                if attempt >= self.max_retries:
                    raise LLMError(f"OpenAI API error after {self.max_retries} retries: {str(e)}", "openai")
        
        return ""
    
    def _call_azure(self, messages: List[Dict[str, str]], temperature: float) -> str:
        """调用 Azure OpenAI API"""
        from openai import OpenAI
        
        client = OpenAI(
            api_key=self.settings.llm_api_key,
            azure_endpoint=self.settings.azure_openai_endpoint,
            api_version="2024-02-01"
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