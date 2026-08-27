"""文件工具：在工作目录（沙箱）内读写文件、列目录、精确替换。

安全设计：所有路径都先解析为绝对路径，并校验其落在工作目录之内，
拒绝 `..` 之类的越界访问，把 agent 的文件操作限制在沙箱内。
"""

import os

from ..errors import PathEscapeError
from .base import truncate

# read_file 默认最多读取的行数，防止超大文件撑爆上下文
DEFAULT_MAX_LINES = 2000


class FileTools:
    def __init__(self, workspace: str):
        self.workspace = os.path.abspath(workspace)

    # ---- 路径安全 -----------------------------------------------------

    def _resolve(self, path: str) -> str:
        """把相对路径解析为工作目录内的绝对路径，并校验不越界。"""
        p = os.path.abspath(os.path.join(self.workspace, path))
        try:
            common = os.path.commonpath([self.workspace, p])
        except ValueError:
            raise PathEscapeError(f"路径无效：{path}")
        if common != self.workspace:
            raise PathEscapeError(f"路径越界，超出工作目录：{path}")
        return p

    @staticmethod
    def _rel(p: str, workspace: str) -> str:
        return os.path.relpath(p, workspace)

    # ---- 工具 ---------------------------------------------------------

    def read_file(self, path: str, start_line=None, end_line=None) -> str:
        p = self._resolve(path)
        if not os.path.isfile(p):
            return f"错误：文件不存在：{path}"
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except Exception as exc:  # noqa: BLE001
            return f"错误：读取失败：{exc}"

        total = len(lines)
        start = max(1, int(start_line) if start_line is not None else 1)
        end = min(total, int(end_line) if end_line is not None else total)

        if start > total or start > end:
            return f"错误：行号范围无效（文件共 {total} 行）"

        shown = lines[start - 1 : end]
        if len(shown) > DEFAULT_MAX_LINES:
            shown = shown[:DEFAULT_MAX_LINES]
            note = f"\n……（仅显示前 {DEFAULT_MAX_LINES} 行，文件共 {total} 行）"
        elif end < total:
            note = f"\n……（已显示到第 {end} 行，文件共 {total} 行）"
        else:
            note = ""

        body = "".join(f"{i:5d} | {shown[idx]}" for idx, i in enumerate(range(start, start + len(shown))))
        return f"文件 {self._rel(p, self.workspace)}（共 {total} 行，显示 {start}-{start + len(shown) - 1} 行）\n{body}{note}"

    def write_file(self, path: str, content: str) -> str:
        p = self._resolve(path)
        parent = os.path.dirname(p)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)
        try:
            with open(p, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as exc:  # noqa: BLE001
            return f"错误：写入失败：{exc}"
        return f"已写入 {self._rel(p, self.workspace)}（{len(content)} 字符）"

    def edit_file(self, path: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
        p = self._resolve(path)
        if not os.path.isfile(p):
            return f"错误：文件不存在：{path}"
        try:
            with open(p, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception as exc:  # noqa: BLE001
            return f"错误：读取失败：{exc}"

        count = text.count(old_string)
        if count == 0:
            return "错误：未找到要替换的内容。请先 read_file 确认文件当前内容，确保 old_string 完全一致（含缩进）。"
        if not replace_all and count > 1:
            return (
                f"错误：old_string 出现 {count} 次，不够唯一。"
                "请提供更长的上下文使其唯一，或设置 replace_all=true。"
            )

        new_text = text.replace(old_string, new_string) if replace_all else text.replace(old_string, new_string, 1)
        try:
            with open(p, "w", encoding="utf-8") as f:
                f.write(new_text)
        except Exception as exc:  # noqa: BLE001
            return f"错误：写入失败：{exc}"
        replaced = count if replace_all else 1
        return f"已替换 {replaced} 处。文件：{self._rel(p, self.workspace)}"

    def list_directory(self, path: str = ".", recursive: bool = False, max_depth: int = 2) -> str:
        p = self._resolve(path)
        if not os.path.isdir(p):
            return f"错误：目录不存在：{path}"

        IGNORE = {".git", "__pycache__", ".venv", "venv", "node_modules", ".pytest_cache"}
        lines = []

        if recursive:
            for root, dirs, files in os.walk(p):
                dirs[:] = [d for d in dirs if d not in IGNORE]
                depth = root[len(p) :].count(os.sep)
                if depth >= max_depth:
                    dirs[:] = []
                for name in sorted(dirs + files):
                    rel = os.path.relpath(os.path.join(root, name), p)
                    lines.append(rel)
        else:
            entries = sorted(os.listdir(p))
            for name in entries:
                if name in IGNORE:
                    continue
                full = os.path.join(p, name)
                tag = "DIR " if os.path.isdir(full) else "FILE"
                lines.append(f"{tag} {name}")

        return truncate("\n".join(lines)) if lines else "（空目录）"
