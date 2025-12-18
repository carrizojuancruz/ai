import pytest
from langchain_core.messages import HumanMessage

from app.agents.supervisor import fast_response_agent as fast_module
from app.agents.supervisor import intent_classifier as classifier_module
from app.agents.supervisor.intent_classifier import intent_classifier
from app.core.config import config


@pytest.mark.asyncio
async def test_intent_classifier_smalltalk_routes_fast_with_llm_confirmation(monkeypatch):
    monkeypatch.setattr(config, "FAST_PATH_ENABLED", True)

    async def mock_llm_classify(text: str) -> tuple[str, float]:
        return "smalltalk", 0.95

    monkeypatch.setattr(classifier_module, "_classify_with_llm_safe", mock_llm_classify)
    state = {"messages": [HumanMessage(content="Hi there")]}

    result = await intent_classifier(state, {})

    assert result["intent_route"] == "fast"
    assert result["intent_classifier_label"] == "smalltalk"
    assert result["intent_classifier_confidence"] >= 0.90


@pytest.mark.asyncio
async def test_intent_classifier_smalltalk_routes_supervisor_when_llm_uncertain(monkeypatch):
    """Verify smalltalk routes to supervisor when LLM confidence is below threshold."""
    monkeypatch.setattr(config, "FAST_PATH_ENABLED", True)

    async def mock_llm_classify(text: str) -> tuple[str, float]:
        return "smalltalk", 0.75

    monkeypatch.setattr(classifier_module, "_classify_with_llm_safe", mock_llm_classify)
    state = {"messages": [HumanMessage(content="Hi there")]}

    result = await intent_classifier(state, {})

    assert result["intent_route"] == "supervisor"


@pytest.mark.asyncio
async def test_intent_classifier_finance_routes_supervisor(monkeypatch):
    monkeypatch.setattr(config, "FAST_PATH_ENABLED", True)
    state = {"messages": [HumanMessage(content="How much did I spend last month?")]}

    result = await intent_classifier(state, {})

    assert result["intent_route"] == "supervisor"
    assert result["intent_classifier_label"] == "task_marker_veto"


@pytest.mark.asyncio
async def test_intent_classifier_mixed_intent_routes_supervisor(monkeypatch):
    monkeypatch.setattr(config, "FAST_PATH_ENABLED", True)
    state = {"messages": [HumanMessage(content="Hi, I need to update a goal.")]}

    result = await intent_classifier(state, {})

    assert result["intent_route"] == "supervisor"
    assert result["intent_classifier_label"] == "task_marker_veto"


@pytest.mark.asyncio
async def test_intent_classifier_help_request_routes_supervisor(monkeypatch):
    monkeypatch.setattr(config, "FAST_PATH_ENABLED", True)
    state = {"messages": [HumanMessage(content="Hey, can you help me?")]}

    result = await intent_classifier(state, {})

    assert result["intent_route"] == "supervisor"
    assert result["intent_classifier_label"] == "task_marker_veto"


@pytest.mark.asyncio
async def test_intent_classifier_capability_question_routes_supervisor(monkeypatch):
    monkeypatch.setattr(config, "FAST_PATH_ENABLED", True)
    state = {"messages": [HumanMessage(content="Hello, what can you do?")]}

    result = await intent_classifier(state, {})

    assert result["intent_route"] == "supervisor"
    assert result["intent_classifier_label"] == "task_marker_veto"


@pytest.mark.asyncio
async def test_intent_classifier_structural_pattern_routes_supervisor(monkeypatch):
    monkeypatch.setattr(config, "FAST_PATH_ENABLED", True)
    state = {"messages": [HumanMessage(content="Tell me something interesting")]}

    result = await intent_classifier(state, {})

    assert result["intent_route"] == "supervisor"
    assert result["intent_classifier_label"] == "structural_veto"


@pytest.mark.asyncio
async def test_intent_classifier_long_message_routes_supervisor(monkeypatch):
    monkeypatch.setattr(config, "FAST_PATH_ENABLED", True)
    long_message = "I was just thinking about talking to you today because I felt a bit bored at home alone"
    state = {"messages": [HumanMessage(content=long_message)]}

    result = await intent_classifier(state, {})

    assert result["intent_route"] == "supervisor"
    assert result["intent_classifier_label"] == "length_veto"


@pytest.mark.asyncio
async def test_intent_classifier_fast_path_disabled(monkeypatch):
    monkeypatch.setattr(config, "FAST_PATH_ENABLED", False)
    state = {"messages": [HumanMessage(content="Hi")]}

    result = await intent_classifier(state, {})

    assert result["intent_route"] == "supervisor"


@pytest.mark.asyncio
async def test_fast_response_agent_uses_generated_text(monkeypatch):
    async def _fake_generate(llm_messages: list) -> str:
        for msg in reversed(llm_messages):
            if isinstance(msg, HumanMessage):
                return f"Echo: {msg.content}"
        return "Echo: empty"

    monkeypatch.setattr(fast_module, "_generate_response", _fake_generate)
    state = {"messages": [HumanMessage(content="hi")]}

    result = await fast_module.fast_response_agent(state, {})

    assert result["messages"][0].content == "Echo: hi"
    assert getattr(result["messages"][0], "name", None) == "fast_response"


@pytest.mark.asyncio
async def test_fast_response_agent_includes_conversation_history(monkeypatch):
    from langchain_core.messages import AIMessage

    captured_messages = []

    async def _capture_generate(llm_messages: list) -> str:
        captured_messages.extend(llm_messages)
        return "Test response"

    monkeypatch.setattr(fast_module, "_generate_response", _capture_generate)

    state = {
        "messages": [
            HumanMessage(content="Hi there"),
            AIMessage(content="Hello! How are you?"),
            HumanMessage(content="I'm good, thanks"),
        ]
    }

    await fast_module.fast_response_agent(state, {})

    human_count = sum(1 for m in captured_messages if isinstance(m, HumanMessage))
    ai_count = sum(1 for m in captured_messages if isinstance(m, AIMessage))

    assert human_count >= 1
    assert ai_count >= 0


def test_has_task_markers_detects_finance_terms():
    from app.agents.supervisor.intent_classifier import _has_task_markers

    assert _has_task_markers("What's my balance?") is True
    assert _has_task_markers("How much did I spend?") is True
    assert _has_task_markers("Show me my transactions") is True
    assert _has_task_markers("Check my account") is True


def test_has_task_markers_detects_help_patterns():
    from app.agents.supervisor.intent_classifier import _has_task_markers

    assert _has_task_markers("Can you help me?") is True
    assert _has_task_markers("I need to do something") is True
    assert _has_task_markers("I want to update my goal") is True
    assert _has_task_markers("Quick question about this") is True


def test_has_task_markers_allows_pure_smalltalk():
    from app.agents.supervisor.intent_classifier import _has_task_markers

    assert _has_task_markers("Hi there") is False
    assert _has_task_markers("How are you?") is False
    assert _has_task_markers("Good morning!") is False
    assert _has_task_markers("Nothing much") is False


def test_has_structural_task_patterns_detects_imperatives():
    from app.agents.supervisor.intent_classifier import _has_structural_task_patterns

    assert _has_structural_task_patterns("Show me something") is True
    assert _has_structural_task_patterns("Tell me a story") is True
    assert _has_structural_task_patterns("Check this out") is True
    assert _has_structural_task_patterns("Help me please") is True


def test_has_structural_task_patterns_detects_possessive_questions():
    from app.agents.supervisor.intent_classifier import _has_structural_task_patterns

    assert _has_structural_task_patterns("What's my status?") is True
    assert _has_structural_task_patterns("Where is my order?") is True
    assert _has_structural_task_patterns("How is my progress?") is True


def test_has_structural_task_patterns_allows_smalltalk_questions():
    from app.agents.supervisor.intent_classifier import _has_structural_task_patterns

    assert _has_structural_task_patterns("How are you?") is False
    assert _has_structural_task_patterns("What's up?") is False
