编程智能体（coding agent）

Git 仓库地址：https://github.com/sy0920/coding-agent-project

一、如何运行
1. 安装依赖：pip install -r requirements.txt
2. 配置密钥：复制 .env.example 为 .env，填入 DEEPSEEK_API_KEY（或用环境变量）
3. 单次任务：python -m coding_agent "写一个统计词频的 Python 脚本"
4. 交互模式：python -m coding_agent（多轮会话、每轮自动保存，支持 /save /resume /switch /sessions /clear）
5. 常用参数：--workspace 指定工作目录；--max-iterations 限制迭代轮数；--verbose 打印过程；--approve 把写文件等改动操作也纳入逐条审批
6. 运行测试：python -m pytest（离线，不消耗 API）

二、特色功能
1. 完整 agent 循环：思考—行动—观察，直到产出最终回答或调用 finish 工具；模型回复流式实时打印。
2. 会话管理：多轮会话记忆 + 持久化；每轮自动落盘，退出时由模型总结生成会话标题；支持 /save、/resume、/switch、/sessions、/clear。
3. 自研工具系统：9 个工具（读写/替换文件、列目录、搜索、执行命令、git、todo、finish），全部本地执行。
4. 任务规划：todo 工具让模型先列计划、完成后更新，完成项打 ✓、未完成项打 ✗ 并附原因。
5. 三级风险审批：只读操作永不审批，执行命令默认审批，--approve 再把写文件等改动操作纳入逐条审批。
6. 项目规则：自动读取工作目录 AGENTS.md / CLAUDE.md 注入系统提示词。
7. 上下文管理：自研 token 估算，超预算时摘要式压缩，压缩后消息结构仍合法。
8. 多重终止条件：无工具调用即结束、finish 工具、最大迭代上限、重复死循环检测。
9. 错误处理：工具异常反馈给模型自纠正；参数 JSON 非法时回传错误；命令超时；API 重试退避。
10. 安全：文件与命令均限制在工作目录沙箱内，拒绝路径越界。
11. 重要逻辑全部自研，仅用 openai 官方客户端库访问 DeepSeek 接口。

三、说明
- 语言 Python；模型 DeepSeek（deepseek-chat，OpenAI 兼容接口）。
- 密钥只通过环境变量或 .env 提供，绝不入库。
- 单元测试离线可跑，不消耗 API 额度。
