"""会话持久化：把对话历史保存到磁盘、恢复、列出。

Conversation.messages 本就是标准 OpenAI 格式的 dict 列表（含 tool_calls），
可直接 JSON 序列化，因此保存/恢复只需 json.dump / json.load，无需任何额外格式转换。
"""

import json
import os

from .context import Conversation


class SessionStore:
    """管理磁盘上的会话文件（每个会话对应一个 <名字>.json）。"""

    def __init__(self, directory: str):
        self.directory = directory

    def _path(self, name: str) -> str:
        # 拒绝含路径分隔符或 ".." 的名字，防止逃出会话目录
        if not name or any(c in name for c in ("/", "\\")) or ".." in name:
            raise ValueError(f"非法会话名：{name!r}")
        return os.path.join(self.directory, name + ".json")

    def save(self, name: str, conversation: Conversation) -> str:
        """保存会话，返回文件路径。同名覆盖。"""
        os.makedirs(self.directory, exist_ok=True)
        path = self._path(name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(conversation.to_dict(), f, ensure_ascii=False, indent=2)
        return path

    def load(self, name: str, max_context_tokens: int) -> Conversation:
        """载入已保存的会话。"""
        with open(self._path(name), "r", encoding="utf-8") as f:
            data = json.load(f)
        return Conversation.from_dict(data, max_context_tokens)

    def delete(self, name: str) -> bool:
        """删除指定会话文件；不存在时返回 False。"""
        try:
            path = self._path(name)
        except ValueError:
            return False
        if os.path.isfile(path):
            os.remove(path)
            return True
        return False

    def exists(self, name: str) -> bool:
        try:
            return os.path.isfile(self._path(name))
        except ValueError:
            return False

    def list_names(self) -> list:
        """列出所有已保存会话的名字（按字母序）。"""
        if not os.path.isdir(self.directory):
            return []
        return sorted(
            os.path.splitext(fn)[0]
            for fn in os.listdir(self.directory)
            if fn.endswith(".json")
        )
