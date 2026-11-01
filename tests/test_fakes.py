"""Check scripted replies and their simple format."""

import ast
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from agent_lab.fakes import FakeChatModel, FakeModel, ScriptExhausted, builtin, load_script


def test_fake_model():
    fake = FakeModel(builtin("two_tool"))
    messages = [{"role": "user", "content": "start"}]
    assert fake.chat(messages).tool_calls[0].id == "call_1"
    messages[0]["content"] = "changed"
    assert fake.requests[0]["messages"][0]["content"] == "start"
    assert fake.chat(messages).tool_calls[0].id == "call_2"
    assert "391" in fake.chat(messages).text
    assert len(fake.requests) == 3
    with pytest.raises(ScriptExhausted):
        fake.chat(messages)


def test_two_calls_and_script_validation(tmp_path):
    script = [{"tool_calls": [{"name": "a", "arguments": "{}"},
                              {"name": "b", "arguments": "{}"}]},
              {"tool_calls": [{"name": "c", "arguments": "{}"}]}]
    fake = FakeModel(script)
    assert [call.id for call in fake.chat([]).tool_calls] == ["call_1", "call_2"]
    assert fake.chat([]).tool_calls[0].id == "call_3"
    assert load_script(script) == script
    assert load_script(script) is not script
    path = tmp_path / "script.json"
    path.write_text('[{"text":"hello"}]', encoding="utf-8")
    assert load_script(path) == load_script(str(path)) == [{"text": "hello"}]
    for invalid in ([{"text": "x", "tool_calls": []}],
                    [{"tool_calls": [{"name": "a", "arguments": "{"}]}],
                    {"text": "x"}):
        with pytest.raises(ValueError, match="reply 0"):
            load_script(invalid)
    with pytest.raises(ValueError, match="missing.json"):
        load_script(tmp_path / "missing.json")
    path.write_text('{"text":"hello"}', encoding="utf-8")
    with pytest.raises(ValueError, match="script.json"):
        load_script(path)


def test_fake_chat_model():
    fake = FakeChatModel(builtin("two_tool"))
    assert fake.bind_tools(["multiply"]) is fake
    assert fake.bound_tools == ["multiply"]
    first = fake.invoke([HumanMessage(content="start")])
    assert isinstance(first, AIMessage)
    assert first.tool_calls[0]["args"] == {"a": 17, "b": 23}
    assert first.tool_calls[0]["id"] == "call_1"
    assert fake.invoke([HumanMessage(content="next")]).tool_calls[0]["id"] == "call_2"
    assert "391" in fake.invoke([HumanMessage(content="done")]).content
    assert len(fake.requests) == 3
    with pytest.raises(ScriptExhausted):
        fake.invoke([HumanMessage(content="again")])


@pytest.mark.parametrize("name", ["model.py", "fakes.py"])
def test_plain_english_docstrings(name):
    path = Path(__file__).resolve().parents[1] / "src" / "agent_lab" / name
    source = path.read_text(encoding="utf-8")
    assert "http://" not in source and "https://" not in source
    tree = ast.parse(source)
    assert ast.get_docstring(tree)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            doc = ast.get_docstring(node)
            assert doc, f"{name}: {node.name} needs a docstring"
            assert all(len(sentence.split()) <= 20 for sentence in doc.split(". "))
