"""coding-agent：一个基于大语言模型（DeepSeek）的自主编程智能体。

核心逻辑（agent 循环、工具定义与本地执行、模型输出解析、上下文管理、
循环终止条件、错误处理）均为自研；仅使用 openai 官方客户端库访问
DeepSeek 的 OpenAI 兼容接口。
"""

__version__ = "1.0.0"
