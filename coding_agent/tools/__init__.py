"""工具集合：定义并注册 agent 可用的全部工具。"""

from .base import Tool, ToolRegistry, truncate
from .command_tool import CommandTool
from .file_tools import FileTools
from .search_tool import SearchTool

__all__ = ["Tool", "ToolRegistry", "truncate", "build_registry"]


def build_registry(config) -> ToolRegistry:
    """按配置构建并注册所有工具，返回注册表。"""
    registry = ToolRegistry()
    file_tools = FileTools(config.workspace)
    command_tool = CommandTool(config.workspace, timeout=config.command_timeout)
    search_tool = SearchTool(config.workspace)

    registry.register(Tool(
        name="list_directory",
        description="列出工作目录（或其子目录）中的文件与文件夹。",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "相对工作目录的路径，默认 '.'"},
                "recursive": {"type": "boolean", "description": "是否递归列出，默认 false"},
                "max_depth": {"type": "integer", "description": "递归时最大深度，默认 2"},
            },
            "required": [],
        },
        func=file_tools.list_directory,
    ))

    registry.register(Tool(
        name="read_file",
        description="读取文件内容（带行号）。",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "要读取的文件路径（相对工作目录）"},
                "start_line": {"type": "integer", "description": "起始行号（1 起，可选）"},
                "end_line": {"type": "integer", "description": "结束行号（含，可选）"},
            },
            "required": ["path"],
        },
        func=file_tools.read_file,
    ))

    registry.register(Tool(
        name="write_file",
        description="创建或覆盖一个文件，写入完整内容。",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "要写入的文件路径（相对工作目录）"},
                "content": {"type": "string", "description": "完整的文件内容"},
            },
            "required": ["path", "content"],
        },
        func=file_tools.write_file,
    ))

    registry.register(Tool(
        name="edit_file",
        description="对文件做精确的字符串替换（把 old_string 替换为 new_string）。",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径（相对工作目录）"},
                "old_string": {"type": "string", "description": "要替换的原文，须与文件内容完全一致"},
                "new_string": {"type": "string", "description": "替换后的新内容"},
                "replace_all": {"type": "boolean", "description": "是否替换所有匹配，默认 false（仅替换第一处）"},
            },
            "required": ["path", "old_string", "new_string"],
        },
        func=file_tools.edit_file,
    ))

    registry.register(Tool(
        name="search_content",
        description="在工作目录内用正则表达式搜索文件内容。",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "要搜索的正则表达式"},
                "path": {"type": "string", "description": "搜索目录（相对工作目录），默认 '.'"},
                "file_glob": {"type": "string", "description": "文件名通配符，默认 '*'"},
                "max_results": {"type": "integer", "description": "最大结果数，默认 50"},
            },
            "required": ["pattern"],
        },
        func=search_tool.search_content,
    ))

    registry.register(Tool(
        name="run_command",
        description="在工作目录中执行一条 shell 命令并返回输出。",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "要执行的 shell 命令"},
            },
            "required": ["command"],
        },
        func=command_tool.run_command,
    ))

    registry.register(Tool(
        name="finish",
        description="任务完成后调用，向用户汇报结果。调用后 agent 会立即结束。",
        parameters={
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "任务完成情况的简洁总结"},
            },
            "required": ["summary"],
        },
        func=lambda summary: f"任务已结束：{summary}",
    ))

    return registry
