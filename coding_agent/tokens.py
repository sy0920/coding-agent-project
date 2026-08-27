"""token 估算。

不依赖外部 tokenizer（避免引入 tiktoken 等重量级依赖），使用一个保守的
启发式估算：CJK 字符按 1 token/字计算，其余字符按 4 字符/token 计算。
该估算对中文偏保守（高估），在上下文压缩决策中更安全——宁可提前压缩，
也不愿超出模型的上下文窗口。
"""

import json
import re

_CJK_RE = re.compile(r"[一-鿿㐀-䶿豈-﫿]")


def estimate_tokens(text: str) -> int:
    """估算单个文本的 token 数。"""
    if not text:
        return 0
    cjk = len(_CJK_RE.findall(text))
    other = len(text) - cjk
    return cjk + (other + 3) // 4


def _content_to_text(content) -> str:
    """把消息的 content 字段归一化为纯文本（兼容字符串与多模态列表）。"""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for p in content:
            if isinstance(p, dict) and isinstance(p.get("text"), str):
                parts.append(p["text"])
        return "".join(parts)
    return str(content)


def estimate_messages_tokens(messages) -> int:
    """估算一组消息的总 token 数（含工具调用参数）。"""
    total = 0
    for m in messages:
        total += estimate_tokens(_content_to_text(m.get("content")))
        for tc in m.get("tool_calls") or []:
            total += estimate_tokens(json.dumps(tc, ensure_ascii=False))
        # tool 结果消息的 content 已在上方计入，这里无需重复。
    return total
