"""LLM 客户端：封装 DeepSeek 的 OpenAI 兼容接口。

这里只负责「与模型对话」这一件事：发请求、解析返回的 tool_calls、以及为
上下文压缩提供摘要能力。agent 循环、工具执行、终止判断等都在别处。

说明：openai 库在此仅作为「模型厂商的 API 客户端库」使用（题目明确允许），
不提供任何 agent 框架能力。
"""

import time
from dataclasses import dataclass, field
from typing import Any, Optional

from openai import OpenAI

from .errors import LLMError
from .parsing import ToolCall, parse_tool_calls, parse_streamed_tool_calls


@dataclass
class LLMResponse:
    """一次模型调用的结构化返回。"""

    content: Optional[str]
    tool_calls: list  # list[ToolCall]
    finish_reason: str
    usage: dict = field(default_factory=dict)


class LLMClient:
    """DeepSeek 客户端封装。"""

    def __init__(self, config):
        if not config.api_key:
            raise LLMError(
                "未设置 API Key。请设置环境变量 DEEPSEEK_API_KEY，"
                "或在项目根目录创建 .env 文件（参考 .env.example）。"
            )
        self.config = config
        self.client = OpenAI(api_key=config.api_key, base_url=config.base_url)

    def chat(self, messages, tools=None, max_retries: int = 3) -> LLMResponse:
        """发送一轮对话。tools 为 OpenAI 兼容的工具列表，None 表示纯文本对话。"""
        last_err: Optional[Exception] = None
        for attempt in range(max_retries):
            try:
                resp = self.client.chat.completions.create(**self._build_kwargs(messages, tools))
                msg = resp.choices[0].message
                return LLMResponse(
                    content=msg.content,
                    tool_calls=parse_tool_calls(msg.tool_calls),
                    finish_reason=getattr(msg, "finish_reason", ""),
                    usage=self._extract_usage(resp),
                )
            except Exception as exc:  # noqa: BLE001 —— 网络/限流/超时等均视为可重试
                last_err = exc
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # 简单指数退避：1s、2s
        raise LLMError(f"调用模型失败（已重试 {max_retries} 次）：{last_err}")

    def chat_stream(
        self, messages, tools=None, on_text=None, max_retries: int = 3
    ) -> LLMResponse:
        """流式发送一轮对话，返回与非流式 chat 完全一致的 LLMResponse。

        与非流式的唯一区别：模型吐出的文本会边收边通过 on_text(text) 回调交给
        调用方（供 CLI 实时打印），而不是等整段回包后一次性返回。工具调用的
        流式分片在内部累积、流结束后才解析，因此对上层完全不可见。
        """
        on_text = on_text or (lambda text: None)
        last_err: Optional[Exception] = None
        for attempt in range(max_retries):
            try:
                return self._stream_once(messages, tools, on_text)
            except Exception as exc:  # noqa: BLE001 —— 网络/限流/超时等均视为可重试
                last_err = exc
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
        raise LLMError(f"调用模型失败（已重试 {max_retries} 次）：{last_err}")

    def _stream_once(self, messages, tools, on_text) -> LLMResponse:
        kwargs = self._build_kwargs(messages, tools)
        kwargs["stream"] = True
        # 让最后一个 chunk 携带 usage，保证 token 统计与上下文压缩预算不因流式而丢
        kwargs["stream_options"] = {"include_usage": True}
        stream = self.client.chat.completions.create(**kwargs)

        content_parts: list = []
        # 流式协议里 tool_calls 按 index 分片：id/name 只在首片，arguments 逐片拼接。
        # 这里跨 chunk 累积成 {index: {id, name, arguments}}，流结束后再统一解析。
        slots: dict = {}
        finish_reason = ""
        usage: dict = {}

        for chunk in stream:
            if getattr(chunk, "usage", None) is not None:
                usage = self._extract_usage(chunk)
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            delta = getattr(choice, "delta", None)
            if delta is None:
                continue

            # 文本增量：直接透传给 on_text，实现逐字输出
            if delta.content:
                content_parts.append(delta.content)
                on_text(delta.content)

            # 工具调用增量：按 index 累积
            for tc_delta in delta.tool_calls or []:
                slot = slots.setdefault(
                    tc_delta.index, {"id": "", "name": "", "arguments": ""}
                )
                if tc_delta.id:
                    slot["id"] = tc_delta.id
                fn = getattr(tc_delta, "function", None)
                if fn is not None:
                    if fn.name:
                        slot["name"] = fn.name
                    if fn.arguments:
                        slot["arguments"] += fn.arguments

            if getattr(choice, "finish_reason", None):
                finish_reason = choice.finish_reason

        content = "".join(content_parts) or None
        return LLMResponse(
            content=content,
            tool_calls=parse_streamed_tool_calls(slots),
            finish_reason=finish_reason,
            usage=usage,
        )

    def summarize(self, text: str, max_tokens: int = 512) -> str:
        """对一段对话历史做摘要，用于上下文压缩。"""
        try:
            resp = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "你是对话摘要助手。请用简洁的中文总结以下编程 agent 的对话历史，"
                            "保留关键事实：任务目标、已修改的文件、命令执行结果、"
                            "尚未解决的问题、后续待办。不要遗漏重要细节。"
                        ),
                    },
                    {"role": "user", "content": text},
                ],
                temperature=0.0,
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content or ""
        except Exception as exc:  # noqa: BLE001 —— 摘要失败不应中断主流程
            return f"（摘要失败：{exc}）"

    def _build_kwargs(self, messages, tools) -> dict:
        kwargs: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        return kwargs

    @staticmethod
    def _extract_usage(resp) -> dict:
        u = getattr(resp, "usage", None)
        if u is None:
            return {}
        return {
            "prompt_tokens": getattr(u, "prompt_tokens", 0),
            "completion_tokens": getattr(u, "completion_tokens", 0),
            "total_tokens": getattr(u, "total_tokens", 0),
        }
