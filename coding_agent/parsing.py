"""模型输出的解析。

把 LLM 返回的 tool_calls（客户端库解码后的对象）解析为自定义的 ToolCall
结构，并在这里处理参数 JSON 的合法性：参数必须是 JSON 对象，非法时记录
parse_error，交由上层把错误反馈给模型（而不是直接崩溃）。
"""

import json
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ToolCall:
    """一次工具调用的结构化表示。"""

    id: str
    name: str
    arguments: dict = field(default_factory=dict)
    parse_error: Optional[str] = None  # 参数 JSON 解析失败时的说明

    def to_api_dict(self) -> dict:
        """转回 OpenAI 兼容的消息格式，用于回传历史。"""
        return {
            "id": self.id,
            "type": "function",
            "function": {
                "name": self.name,
                "arguments": json.dumps(self.arguments, ensure_ascii=False),
            },
        }


def parse_tool_calls(raw_tool_calls) -> list:
    """解析模型返回的 tool_calls 列表为自定义 ToolCall 列表。"""
    result = []
    for tc in raw_tool_calls or []:
        name = tc.function.name
        raw_args = tc.function.arguments or ""
        arguments = {}
        parse_error = None
        try:
            arguments = json.loads(raw_args) if raw_args.strip() else {}
            if not isinstance(arguments, dict):
                parse_error = f"参数应为 JSON 对象，实际为 {type(arguments).__name__}"
                arguments = {}
        except json.JSONDecodeError as exc:
            parse_error = f"参数不是合法 JSON：{exc}"
        result.append(
            ToolCall(id=tc.id, name=name, arguments=arguments, parse_error=parse_error)
        )
    return result
