"""任务清单工具：让 agent 在多步任务中显式维护计划。

实现为内存中的简单列表，agent 通过 todo 工具整体覆盖写入；模型在后续轮次里
可从工具返回结果中看到当前清单，从而对「已完成 / 待办」保持掌控。
"""


class TodoTool:
    def __init__(self):
        self._todos: list = []

    def set_todos(self, todos: list) -> str:
        """用给定列表整体覆盖当前任务清单；空列表表示清空。

        每项既可以是字符串（视为待办），也可以是 {"text", "done", "note"} 对象。
        渲染规则：done=true 打 ✓；未完成且写了 note 的打 ✗ 并附原因；其余（待办）
        保持中性，不加标记——这样任务中途列计划时不突兀，收尾时才区分完成/未完成。
        """
        self._todos = todos
        if not self._todos:
            return "（任务清单已清空）"
        lines = []
        for i, item in enumerate(todos, 1):
            text, done, note = self._normalize(item)
            if done:
                mark = "✓ "
            elif note:
                mark = "✗ "
            else:
                mark = ""
            suffix = f"（未完成：{note}）" if (not done and note) else ""
            lines.append(f"{mark}{i}. {text}{suffix}")
        return "当前任务清单：\n" + "\n".join(lines)

    @staticmethod
    def _normalize(item) -> tuple:
        """把 todo 项统一成 (text, done, note)；兼容字符串与对象两种写法。"""
        if isinstance(item, dict):
            text = str(item.get("text", ""))
            done = bool(item.get("done", False))
            note = str(item.get("note", "") or "")
        else:
            text, done, note = str(item), False, ""
        return text, done, note
