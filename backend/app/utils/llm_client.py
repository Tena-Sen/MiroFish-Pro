"""
LLM客户端封装
统一使用OpenAI格式调用
"""

import json
import logging
import re
import time
from typing import Optional, Dict, Any, List
from openai import OpenAI, AsyncOpenAI
from openai._exceptions import APIConnectionError, APITimeoutError

from ..config import Config

logger = logging.getLogger(__name__)


def _is_unsupported_temperature_error(e: Exception) -> bool:
    """判断异常是否为 'temperature 参数不受支持' 类 400 错误（如 kimi-k3）。

    这类模型不支持传入 temperature，需要去掉该参数后重试。
    """
    msg = str(e).lower()
    return "'temperature'" in msg and ("not supported" in msg or "unsupported" in msg)


def _parse_max_tokens_limit(e: Exception) -> Optional[int]:
    """从服务商 400 错误信息中解析 max_tokens 允许的上限。

    兼容两类报错格式：
    - "Range of max_tokens should be [10, 2048]"（DeepSeek 等）
    - "max_tokens must be at most 2048" / "maximum context length is 2048 tokens"

    返回 None 表示不是 max_tokens 范围类错误。
    """
    msg = str(e)
    if "max_tokens" not in msg.lower():
        return None
    # 格式1: [10, 2048]
    m = re.search(r'\[\s*(\d+)\s*,\s*(\d+)\s*\]', msg)
    if m:
        return int(m.group(2))
    # 格式2: at most / maximum / <= 2048
    m = re.search(r'(?:at most|max(?:imum)?|no more than|<=|≤)\s*(\d+)', msg, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def _create_with_fallbacks(create_fn, kwargs):
    """同步调用 create_fn，遇到已知的参数兼容性问题自动降级重试。

    处理两类问题：
    1. temperature 不受支持（kimi-k3）→ 移除 temperature 后重试
    2. max_tokens 超出服务商上限（部分模型限制 [10, 2048]）→ clamp 到上限重试
    """
    try:
        return create_fn(**kwargs)
    except Exception as e:
        if _is_unsupported_temperature_error(e):
            logger.warning(f"模型不支持 temperature 参数，去掉后重试")
            kwargs = {k: v for k, v in kwargs.items() if k != "temperature"}
            try:
                return create_fn(**kwargs)
            except Exception as e2:
                e = e2  # temperature 降级后仍失败，继续尝试 max_tokens 降级
        limit = _parse_max_tokens_limit(e)
        if limit is not None and limit >= 10 and kwargs.get("max_tokens", 0) > limit:
            logger.warning(
                f"服务商限制 max_tokens ≤ {limit}（原请求 {kwargs.get('max_tokens')}），降级重试"
            )
            kwargs = dict(kwargs, max_tokens=limit)
            return create_fn(**kwargs)
        raise


async def _acreate_with_fallbacks(create_fn, kwargs):
    """异步版 _create_with_fallbacks，降级逻辑完全一致。"""
    try:
        return await create_fn(**kwargs)
    except Exception as e:
        if _is_unsupported_temperature_error(e):
            logger.warning(f"模型不支持 temperature 参数，去掉后重试")
            kwargs = {k: v for k, v in kwargs.items() if k != "temperature"}
            try:
                return await create_fn(**kwargs)
            except Exception as e2:
                e = e2
        limit = _parse_max_tokens_limit(e)
        if limit is not None and limit >= 10 and kwargs.get("max_tokens", 0) > limit:
            logger.warning(
                f"服务商限制 max_tokens ≤ {limit}（原请求 {kwargs.get('max_tokens')}），降级重试"
            )
            kwargs = dict(kwargs, max_tokens=limit)
            return await create_fn(**kwargs)
        raise


class LLMClient:
    """LLM客户端"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model = model or Config.LLM_MODEL_NAME
        
        if not self.api_key:
            raise ValueError("LLM_API_KEY 未配置")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None
    ) -> str:
        """
        发送聊天请求
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            response_format: 响应格式（如JSON模式）
            
        Returns:
            模型响应文本
        """
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        if response_format:
            kwargs["response_format"] = response_format

        response = _create_with_fallbacks(self.client.chat.completions.create, kwargs)
        content = response.choices[0].message.content
        # 部分模型（如MiniMax M2.5）会在content中包含<think>思考内容，需要移除
        content = re.sub(r'<think>[\s\S]*?</think>', '', content).strip()
        return content
    
    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        """
        发送聊天请求并返回JSON
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            
        Returns:
            解析后的JSON对象
        """
        response = self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}
        )
        # 清理markdown代码块标记
        cleaned_response = response.strip()
        cleaned_response = re.sub(r'^```(?:json)?\s*\n?', '', cleaned_response, flags=re.IGNORECASE)
        cleaned_response = re.sub(r'\n?```\s*$', '', cleaned_response)
        cleaned_response = cleaned_response.strip()

        try:
            return json.loads(cleaned_response)
        except json.JSONDecodeError:
            # 尝试提取第一个完整的JSON对象
            try:
                # 找到第一个 { 的位置
                start = cleaned_response.find('{')
                if start == -1:
                    raise ValueError(f"LLM返回中未找到JSON对象: {cleaned_response[:200]}")

                # 从第一个 { 开始，找到匹配的 }
                depth = 0
                end = start
                for i in range(start, len(cleaned_response)):
                    if cleaned_response[i] == '{':
                        depth += 1
                    elif cleaned_response[i] == '}':
                        depth -= 1
                        if depth == 0:
                            end = i + 1
                            break

                json_str = cleaned_response[start:end]
                return json.loads(json_str)
            except (json.JSONDecodeError, ValueError) as e:
                raise ValueError(f"LLM返回的JSON格式无效: {cleaned_response[:200]}")


# =============================================================================
# 异步客户端（Phase 1 新增，与同步版输出等价）
# =============================================================================

class LLMClientAsync:
    """
    LLM 客户端（异步版）

    与 LLMClient 的区别：
    - 底层使用 AsyncOpenAI（不阻塞事件循环）
    - chat / chat_json 是 coroutine，需要用 await 调用
    - 相同的 messages + temperature + model 产出相同的 LLM 响应
      （异步不引入额外随机性，仅改变并发模型）

    典型用法（用 asyncio.Semaphore 控制并发）：
        async def gen_all(items, parallel=30):
            sem = asyncio.Semaphore(parallel)
            client = LLMClientAsync()
            async def one(item):
                async with sem:
                    return await client.chat_json(...)
            return await asyncio.gather(*[one(i) for i in items])
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model = model or Config.LLM_MODEL_NAME

        if not self.api_key:
            raise ValueError("LLM_API_KEY 未配置")

        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None
    ) -> str:
        """
        异步发送聊天请求。

        返回的字符串与 LLMClient.chat 在相同 (model, messages, temperature,
        max_tokens, response_format) 下等价——异步仅改变并发模型。
        """
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if response_format:
            kwargs["response_format"] = response_format

        response = await _acreate_with_fallbacks(self.client.chat.completions.create, kwargs)
        content = response.choices[0].message.content
        # 复用 LLMClient 的清理逻辑（保证输出一致）
        return re.sub(r'<think>[\s\S]*?</think>', '', content).strip()

    async def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        """
        异步发送聊天请求并返回 JSON 对象。

        与 LLMClient.chat_json 解析逻辑完全一致。
        """
        response = await self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}
        )
        # 复用 chat_json 的 markdown 清理 + JSON 提取逻辑
        cleaned_response = response.strip()
        cleaned_response = re.sub(r'^```(?:json)?\s*\n?', '', cleaned_response, flags=re.IGNORECASE)
        cleaned_response = re.sub(r'\n?```\s*$', '', cleaned_response)
        cleaned_response = cleaned_response.strip()

        try:
            return json.loads(cleaned_response)
        except json.JSONDecodeError:
            try:
                start = cleaned_response.find('{')
                if start == -1:
                    raise ValueError(f"LLM返回中未找到JSON对象: {cleaned_response[:200]}")

                depth = 0
                end = start
                for i in range(start, len(cleaned_response)):
                    if cleaned_response[i] == '{':
                        depth += 1
                    elif cleaned_response[i] == '}':
                        depth -= 1
                        if depth == 0:
                            end = i + 1
                            break

                json_str = cleaned_response[start:end]
                return json.loads(json_str)
            except (json.JSONDecodeError, ValueError) as e:
                raise ValueError(f"LLM返回的JSON格式无效: {cleaned_response[:200]}")


def run_async_from_sync(coro):
    """
    在同步上下文中运行 async coroutine 的 helper。

    用于从已有的 ThreadPoolExecutor worker 中调用 asyncio 协程，
    避免与 Flask 主线程的事件循环冲突。

    用法（在线程池 worker 中）：
        result = run_async_from_sync(self._do_async_work(...))
    """
    import asyncio
    import concurrent.futures
    try:
        # 如果当前线程已有 event loop（罕见，但要兜底），用新线程跑
        asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            return ex.submit(asyncio.run, coro).result()
    except RuntimeError:
        # 当前线程没有 loop，直接 asyncio.run
        return asyncio.run(coro)

