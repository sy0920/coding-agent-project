"""工具框架：工具定义、注册表与统一执行入口。

工具即「一个带 JSON Schema 的可调用函数」。框架负责：
- 把工具转成模型可识别的 OpenAI function 格式（定义在本地，非服务端托管）；
- 按名字分发调用；
- 把任何异常统一转成「反馈给模型」的文本结果（而非让 agent 崩溃）。
"""

from dataclasses import dataclass
from typing import Any, Callable

from ..errors import ToolError


@dataclass
class Tool:
    """一个工具：名称、描述、JSON Schema 参数、本地执行函数。"""

    name: str
    description: str
    parameters: dict  # JSON Schema
    func: Callable[..., str]  # 返回「给模型看的」字符串结果

    def to_openai_dict(self) -> dict:
        """转为 OpenAI 兼容的工具定义。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def truncate(text: str, limit: int = 8000) -> str:
    """截断过长的文本，并附注被截断的长度，避免撑爆上下文。"""
    if len(text) > limit:
        return text[:limit] + f"\n……（输出过长已截断，原 {len(text)} 字符）"
    return text


class ToolRegistry:
    """工具的注册与分发。"""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> Tool:
        self._tools[tool.name] = tool
        return tool

    def names(self) -> list:
        return list(self._tools.keys())

    def to_openai_tools(self) -> list:
        return [t.to_openai_dict() for t in self._tools.values()]

    def execute(self, name: str, arguments: dict) -> str:
        """执行工具并返回文本结果；所有异常都被捕获并转成可读的错误文本。"""
        tool = self._tools.get(name)
        if tool is None:
            return f"错误：未知工具「{name}」。可用工具：{', '.join(self.names())}"
        try:
            return tool.func(**arguments)
        except ToolError as exc:
            return f"错误：{exc}"
        except TypeError as exc:
            return f"错误：工具「{name}」的参数不匹配：{exc}"
        except Exception as exc:  # noqa: BLE001 —— 工具内部的意外错误也要反馈给模型
            return f"错误：工具「{name}」执行失败（{type(exc).__name__}）：{exc}"
