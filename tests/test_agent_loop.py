from coding_agent.agent import Agent
from coding_agent.config import Config
from coding_agent.context import Conversation
from coding_agent.llm import LLMResponse
from coding_agent.parsing import ToolCall
from coding_agent.tools import build_registry

from .fakes import FakeLLM


def _config(tmp_path, **kw):
    cfg = Config(api_key="test", workspace=str(tmp_path), max_iterations=10)
    for k, v in kw.items():
        setattr(cfg, k, v)
    return cfg


def _agent(tmp_path, responses, **kw):
    cfg = _config(tmp_path, **kw)
    llm = FakeLLM(responses)
    tools = build_registry(cfg)
    return Agent(llm, tools, cfg, "系统提示词"), llm, cfg


def test_finishes_on_final_answer(tmp_path):
    agent, llm, _ = _agent(tmp_path, [LLMResponse("完成", [], "stop", {})])
    r = agent.run("任务")
    assert r.success and r.stop_reason == "finished"
    assert r.final_answer == "完成" and r.iterations == 1


def test_executes_tool_then_finishes(tmp_path):
    r1 = LLMResponse(None, [ToolCall("c1", "write_file", {"path": "a.txt", "content": "hi"})], "tool_calls", {})
    r2 = LLMResponse("已写好", [], "stop", {})
    agent, llm, _ = _agent(tmp_path, [r1, r2])
    result = agent.run("写文件")
    assert result.success and result.final_answer == "已写好"
    assert (tmp_path / "a.txt").read_text() == "hi"
    assert result.iterations == 2


def test_finish_tool_short_circuits(tmp_path):
    r1 = LLMResponse(None, [ToolCall("c1", "finish", {"summary": "完成啦"})], "tool_calls", {})
    agent, llm, _ = _agent(tmp_path, [r1])
    r = agent.run("任务")
    assert r.success and r.stop_reason == "finish_tool"
    assert r.final_answer == "完成啦"


def test_max_iterations(tmp_path):
    r = LLMResponse(None, [ToolCall("c1", "list_directory", {})], "tool_calls", {})
    cfg = _config(tmp_path, max_iterations=3)
    llm = FakeLLM([r] * 10)
    tools = build_registry(cfg)
    agent = Agent(llm, tools, cfg, "sys")
    result = agent.run("任务")
    assert not result.success and result.stop_reason == "max_iterations"
    assert result.iterations == 3


def test_tool_error_fed_back_to_model(tmp_path):
    r1 = LLMResponse(None, [ToolCall("c1", "no_such_tool", {})], "tool_calls", {})
    r2 = LLMResponse("ok", [], "stop", {})
    agent, llm, _ = _agent(tmp_path, [r1, r2])
    result = agent.run("任务")
    assert result.success
    tool_msgs = [m for m in llm.calls[-1][0] if m["role"] == "tool"]
    assert "未知工具" in tool_msgs[0]["content"]


def test_repetition_guard_injects_hint(tmp_path):
    r = LLMResponse(None, [ToolCall("c1", "list_directory", {})], "tool_calls", {})
    cfg = _config(tmp_path, max_iterations=6)
    llm = FakeLLM([r] * 10)
    tools = build_registry(cfg)
    agent = Agent(llm, tools, cfg, "sys")
    agent.run("任务")
    injected = any(
        "重复循环" in (m.get("content") or "")
        for call in llm.calls
        for m in call[0]
    )
    assert injected


def test_conversation_reuse_across_turns(tmp_path):
    """复用 conversation 时，下一轮模型能看到上一轮的完整历史。"""
    r1 = LLMResponse(
        None, [ToolCall("c1", "write_file", {"path": "a.txt", "content": "hi"})],
        "tool_calls", {},
    )
    r2 = LLMResponse("已写好", [], "stop", {})
    agent, llm, _ = _agent(tmp_path, [r1, r2])

    first = agent.run("写文件")
    assert first.conversation is not None

    # 第二轮复用 first.conversation
    agent.run("再给它加个测试", conversation=first.conversation)
    msgs = llm.calls[-1][0]
    assert msgs[1]["role"] == "user" and msgs[1]["content"] == "写文件"
    assert msgs[-1]["role"] == "user" and msgs[-1]["content"] == "再给它加个测试"
    assert any(m["role"] == "tool" for m in msgs)  # 上一轮的工具结果仍在


def test_run_without_conversation_starts_fresh(tmp_path):
    """不传 conversation 时，每次 run 都是全新上下文（互不影响）。"""
    r = LLMResponse("ok", [], "stop", {})
    agent, llm, _ = _agent(tmp_path, [r, r])
    agent.run("任务1")
    agent.run("任务2")
    second_msgs = llm.calls[-1][0]
    # 第二轮里不应出现第一轮的用户消息
    contents = [m.get("content") for m in second_msgs if m["role"] == "user"]
    assert contents == ["任务2"]


def test_dangerous_tool_rejected_by_approver(tmp_path):
    """审批拒绝时，危险命令不执行，工具结果反馈「拒绝」。"""
    r1 = LLMResponse(
        None, [ToolCall("c1", "run_command", {"command": "echo hi"})], "tool_calls", {}
    )
    r2 = LLMResponse("好", [], "stop", {})
    cfg = _config(tmp_path)
    llm = FakeLLM([r1, r2])
    tools = build_registry(cfg)
    agent = Agent(llm, tools, cfg, "sys", approver=lambda name, args: False)
    agent.run("任务")
    tool_msgs = [m for m in llm.calls[-1][0] if m["role"] == "tool"]
    assert any("拒绝" in m["content"] for m in tool_msgs)
    assert not any("hi" in m["content"] for m in tool_msgs)


def test_dangerous_tool_approved_runs(tmp_path):
    """审批通过时，危险命令正常执行。"""
    r1 = LLMResponse(
        None, [ToolCall("c1", "run_command", {"command": "echo hi"})], "tool_calls", {}
    )
    r2 = LLMResponse("好", [], "stop", {})
    cfg = _config(tmp_path)
    llm = FakeLLM([r1, r2])
    tools = build_registry(cfg)
    agent = Agent(llm, tools, cfg, "sys", approver=lambda name, args: True)
    agent.run("任务")
    tool_msgs = [m for m in llm.calls[-1][0] if m["role"] == "tool"]
    assert any("hi" in m["content"] for m in tool_msgs)


def test_default_mode_does_not_approve_safe_ops(tmp_path):
    """默认（approve_all=False）下，非危险操作即使配置了 approver 也不审批。"""
    r1 = LLMResponse(None, [ToolCall("c1", "list_directory", {})], "tool_calls", {})
    r2 = LLMResponse("完成", [], "stop", {})
    cfg = _config(tmp_path)
    llm = FakeLLM([r1, r2])
    tools = build_registry(cfg)
    # approver 一律拒绝，但 list_directory 非危险、默认不审批 → 仍执行
    agent = Agent(llm, tools, cfg, "sys", approver=lambda name, args: False)
    result = agent.run("任务")
    assert result.success
    tool_msgs = [m for m in llm.calls[-1][0] if m["role"] == "tool"]
    assert not any("拒绝" in m["content"] for m in tool_msgs)


def test_approve_all_rejects_safe_ops(tmp_path):
    """approve_all=True 时，非危险操作也要审批，拒绝则不执行。"""
    r1 = LLMResponse(None, [ToolCall("c1", "list_directory", {})], "tool_calls", {})
    r2 = LLMResponse("完成", [], "stop", {})
    cfg = _config(tmp_path)
    llm = FakeLLM([r1, r2])
    tools = build_registry(cfg)
    agent = Agent(
        llm, tools, cfg, "sys", approver=lambda name, args: False, approve_all=True
    )
    agent.run("任务")
    tool_msgs = [m for m in llm.calls[-1][0] if m["role"] == "tool"]
    assert any("拒绝" in m["content"] for m in tool_msgs)


def test_qa_over_file_flow(tmp_path):
    """「检索→阅读→作答」的基于文件的问答链路能端到端跑通。"""
    (tmp_path / "data.txt").write_text("1\n2\n3\n")
    r1 = LLMResponse(
        None, [ToolCall("c1", "search_content", {"pattern": "data"})], "tool_calls", {}
    )
    r2 = LLMResponse(
        None, [ToolCall("c2", "read_file", {"path": "data.txt"})], "tool_calls", {}
    )
    r3 = LLMResponse("平均值是 2", [], "stop", {})
    agent, _, _ = _agent(tmp_path, [r1, r2, r3])
    result = agent.run("data 文件里的数字平均值是多少")
    assert result.success
    assert result.final_answer == "平均值是 2"


def test_on_step_receives_tool_result(tmp_path):
    """进度回调应收到工具返回结果（供 CLI 打印过程）。"""
    (tmp_path / "a.txt").write_text("hello")
    r1 = LLMResponse(
        None, [ToolCall("c1", "read_file", {"path": "a.txt"})], "tool_calls", {}
    )
    r2 = LLMResponse("完成", [], "stop", {})
    cfg = _config(tmp_path)
    llm = FakeLLM([r1, r2])
    tools = build_registry(cfg)
    steps = []
    agent = Agent(
        llm, tools, cfg, "sys",
        on_step=lambda name, args, result: steps.append((name, result)),
    )
    agent.run("读文件")
    assert any(name == "read_file" and "hello" in result for name, result in steps)


def test_on_step_receives_error_result(tmp_path):
    """工具出错时，错误文本也应通过进度回调传给调用方。"""
    r1 = LLMResponse(
        None, [ToolCall("c1", "no_such_tool", {})], "tool_calls", {}
    )
    r2 = LLMResponse("完成", [], "stop", {})
    cfg = _config(tmp_path)
    llm = FakeLLM([r1, r2])
    tools = build_registry(cfg)
    steps = []
    agent = Agent(
        llm, tools, cfg, "sys",
        on_step=lambda name, args, result: steps.append((name, result)),
    )
    agent.run("任务")
    assert any("未知工具" in result for name, result in steps)


def test_on_step_receives_compact_event(tmp_path, monkeypatch):
    """上下文压缩发生时，进度回调应收到 compact 事件。"""
    r1 = LLMResponse(None, [ToolCall("c1", "list_directory", {})], "tool_calls", {})
    r2 = LLMResponse("完成", [], "stop", {})
    cfg = _config(tmp_path)
    llm = FakeLLM([r1, r2])
    tools = build_registry(cfg)
    steps = []
    agent = Agent(
        llm, tools, cfg, "sys",
        on_step=lambda name, args, result: steps.append((name, args, result)),
    )
    # 真实压缩逻辑已由 test_context 覆盖；这里只验证 agent 把压缩信号转发给 on_step
    monkeypatch.setattr(Conversation, "maybe_compact", lambda self, fn: True)
    agent.run("任务")
    compact = [args for name, args, _ in steps if name == "compact"]
    assert compact
    assert "before" in compact[0] and "after" in compact[0]


def test_on_text_receives_streamed_content(tmp_path):
    """配置 on_text 时 agent 走 chat_stream，最终答案经 on_text 实时回调输出。"""
    r1 = LLMResponse(None, [ToolCall("c1", "list_directory", {})], "tool_calls", {})
    r2 = LLMResponse("答案是 42", [], "stop", {})
    cfg = _config(tmp_path)
    llm = FakeLLM([r1, r2])
    tools = build_registry(cfg)
    received = []
    agent = Agent(llm, tools, cfg, "sys", on_text=received.append)
    result = agent.run("任务")
    assert result.success
    # 只有最终答案轮（有 content）触发回调；工具调用轮 content 为空不回调
    assert received == ["答案是 42"]
