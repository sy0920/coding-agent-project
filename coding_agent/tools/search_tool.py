"""搜索工具：在工作目录内用正则表达式搜索文件内容。

用 Python 自带的 re + os.walk 实现，跨平台（不依赖系统 grep），
并自动跳过 .git / __pycache__ 等无关目录。
"""

import os
import re
from fnmatch import fnmatch

from ..errors import PathEscapeError
from .base import truncate


class SearchTool:
    def __init__(self, workspace: str):
        self.workspace = os.path.abspath(workspace)

    def search_content(self, pattern: str, path: str = ".", file_glob: str = "*", max_results: int = 50) -> str:
        p = os.path.abspath(os.path.join(self.workspace, path))
        try:
            common = os.path.commonpath([self.workspace, p])
        except ValueError:
            return "错误：搜索路径无效"
        if common != self.workspace:
            raise PathEscapeError(f"搜索路径越界：{path}")

        try:
            regex = re.compile(pattern)
        except re.error as exc:
            return f"错误：正则表达式无效：{exc}"

        IGNORE = {".git", "__pycache__", ".venv", "venv", "node_modules", ".pytest_cache"}
        matches = []
        for root, dirs, files in os.walk(p):
            dirs[:] = [d for d in dirs if d not in IGNORE]
            for fn in files:
                if not fnmatch(fn, file_glob):
                    continue
                fp = os.path.join(root, fn)
                try:
                    with open(fp, "r", encoding="utf-8", errors="replace") as f:
                        for i, line in enumerate(f, 1):
                            if regex.search(line):
                                rel = os.path.relpath(fp, self.workspace)
                                matches.append(f"{rel}:{i}: {line.rstrip()}")
                                if len(matches) >= max_results:
                                    return truncate("\n".join(matches))
                except (OSError, UnicodeDecodeError):
                    continue

        return truncate("\n".join(matches)) if matches else "未找到匹配内容"
