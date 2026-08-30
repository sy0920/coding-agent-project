编程智能体（coding agent）

Git 仓库地址：https://github.com/sy0920/coding-agent-project

一、如何运行
1. 安装依赖：pip install -r requirements.txt
2. 配置密钥：复制 .env.example 为 .env，填入 DEEPSEEK_API_KEY（或用环境变量）
3. 单次任务：python -m coding_agent "写一个统计词频的 Python 脚本"
4. 交互模式：python -m coding_agent（多轮会话，输入 clear 清空重来）
5. 常用参数：--workspace 指定工作目录；--max-iterations 限制迭代轮数；--verbose 打印过程
6. 运行测试：python -m pytest（离线，不消耗 API）

二、特色功能
1. 完整 agent 循环：思考—行动—观察，直到产出最终回答或调用 finish 工具。
2. 多轮会话记忆：交互模式下后续输入沿用同一会话，agent 记住上下文；clear 清空重来。
3. 自研工具系统：read_file / write_file / edit_file / list_directory / search_content / run_command / finish，全部在本地执行（非服务端托管）。
4. 上下文管理：自研 token 估算，超预算时摘要式压缩，压缩后消息结构仍合法。
5. 多重终止条件：无工具调用即结束、finish 工具、最大迭代上限、重复调用死循环检测。
6. 错误处理：工具异常反馈给模型自纠正；参数 JSON 非法时回传错误；命令超时；API 重试退避。
7. 安全：文件与命令均限制在工作目录沙箱内，拒绝路径越界。
8. 重要逻辑全部自研，仅用 openai 官方客户端库访问 DeepSeek 接口。

三、说明
- 语言 Python；模型 DeepSeek（deepseek-chat，OpenAI 兼容接口）。
- 密钥只通过环境变量或 .env 提供，绝不入库。
- 单元测试离线可跑，不消耗 API 额度。
