"""自定义异常类型，用于区分不同层级的错误。"""


class AgentError(Exception):
    """agent 运行时的基础错误。"""


class ToolError(AgentError):
    """工具定义或执行过程中的错误。"""


class ToolNotFoundError(ToolError):
    """调用了未注册的工具。"""


class PathEscapeError(ToolError):
    """文件路径越出了工作目录（沙箱）范围。"""


class LLMError(AgentError):
    """调用大模型接口失败（网络、限流、超时等）。"""
