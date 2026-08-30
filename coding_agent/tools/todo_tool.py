"""任务清单工具：让 agent 在多步任务中显式维护计划。

实现为内存中的简单列表，agent 通过 todo 工具整体覆盖写入；模型在后续轮次里
可从工具返回结果中看到当前清单，从而对「已完成 / 待办」保持掌控。
"""


class TodoTool:
    def __init__(self):
        self._todos: list = []

    def set_todos(self, todos: list) -> str:
        """用给定列表整体覆盖当前任务清单；空列表表示清空。"""
        self._todos = [str(t) for t in todos]
        if not self._todos:
            return "（任务清单已清空）"
        lines = [f"{i}. {t}" for i, t in enumerate(self._todos, 1)]
        return "当前任务清单：\n" + "\n".join(lines)
