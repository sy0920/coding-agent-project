from coding_agent.agent import Agent
from coding_agent.config import Config
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
