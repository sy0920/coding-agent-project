"""配置加载：所有可调参数均通过环境变量（或 .env 文件）注入。

API key 等凭据一律走环境变量 / .env（已 gitignore），绝不硬编码进代码。
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# 读取 .env 文件（若存在）；override=False 保证已有的环境变量优先。
load_dotenv()


@dataclass
class Config:
    """agent 的运行时配置。"""

    api_key: str = ""
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-chat"
    workspace: str = "./workspace"
    max_iterations: int = 30
    max_context_tokens: int = 60000
    command_timeout: int = 60
    temperature: float = 0.0
    max_tokens: int = 4096

    @classmethod
    def from_env(cls) -> "Config":
        """从环境变量读取配置，未设置的项使用默认值。"""
        return cls(
            api_key=os.getenv("DEEPSEEK_API_KEY", os.getenv("LLM_API_KEY", "")),
            base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
            model=os.getenv("LLM_MODEL", "deepseek-chat"),
            workspace=os.getenv("AGENT_WORKSPACE", "./workspace"),
            max_iterations=int(os.getenv("AGENT_MAX_ITERATIONS", "30")),
            max_context_tokens=int(os.getenv("AGENT_MAX_CONTEXT_TOKENS", "60000")),
            command_timeout=int(os.getenv("AGENT_COMMAND_TIMEOUT", "60")),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.0")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "4096")),
        )
