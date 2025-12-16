import logging
from typing import Any, Iterable

from langchain_aws import ChatBedrockConverse
from langchain_core.messages import BaseMessage
from langfuse.langchain import CallbackHandler
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agents.supervisor.memory import memory_context, memory_hotpath
from app.agents.supervisor.summarizer import ConversationSummarizer
from app.core.config import config as app_config
from app.services.llm.safe_cerebras import SafeChatCerebras
from app.services.memory.checkpointer import get_supervisor_checkpointer
from app.services.memory.store_factory import create_s3_vectors_store_from_env

from .handoff import create_task_description_handoff_tool
from .subgraph import create_supervisor_subgraph
from .workers import finance_router, goal_agent

logger = logging.getLogger(__name__)

try:  # pragma: no cover - used only by external tests
    from langgraph.checkpoint.memory import MemorySaver as _MemorySaver  # type: ignore

    MemorySaver = _MemorySaver  # re-export for test compatibility
except Exception:  # pragma: no cover
    MemorySaver = None  # type: ignore

CONTEXT_PROFILE_PREFIX: str = "CONTEXT_PROFILE:"
RELEVANT_CONTEXT_PREFIX: str = "Relevant context for tailoring this turn:"
CONTEXT_KEY_MAX_PROMPT_TOKENS_LAST_RUN: str = "max_prompt_tokens_last_run"
CONTEXT_KEY_MAX_TOTAL_TOKENS_LAST_RUN: str = "max_total_tokens_last_run"

SUMMARY_TRIGGER_REASON_PROMPT_TOKENS: str = "prompt_tokens_threshold"
SUMMARY_TRIGGER_REASON_USER_COUNT_FALLBACK: str = "user_message_count_fallback"


def _coerce_int(value: Any, fallback: int) -> int:
    if value is None:
        return fallback
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (ValueError, TypeError):
        return fallback


def _to_plain_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, dict):
                if item.get("type") == "text" and isinstance(item.get("text"), str):
                    parts.append(item["text"])
            elif hasattr(item, "get"):
                try:
                    t = item.get("text")
                    if isinstance(t, str):
                        parts.append(t)
                except (AttributeError, TypeError, KeyError):
                    continue
        return "\n".join([p for p in parts if p])
    content = getattr(value, "content", None)
    if isinstance(content, str):
        return content
    return str(value)


def _is_injected_user_context_message(message: BaseMessage) -> bool:
    msg_type = getattr(message, "type", "")
    if msg_type not in {"human", "user"}:
        return False
    content = _to_plain_text(getattr(message, "content", None)).strip()
    return content.startswith(CONTEXT_PROFILE_PREFIX) or content.startswith(RELEVANT_CONTEXT_PREFIX)


def count_user_messages_for_trigger(messages: Iterable[BaseMessage]) -> int:
    count = 0
    for message in messages:
        msg_type = getattr(message, "type", "")
        if msg_type not in {"human", "user"}:
            continue
        if _is_injected_user_context_message(message):
            continue
        count += 1
    return count


def should_trigger_summarization_at_turn_start(
    *,
    messages: Iterable[BaseMessage],
    context: dict[str, Any],
    trigger_prompt_tokens: int,
    fallback_user_message_count: int,
) -> bool:
    last_prompt_tokens = _coerce_int(context.get(CONTEXT_KEY_MAX_PROMPT_TOKENS_LAST_RUN), 0)
    if last_prompt_tokens >= trigger_prompt_tokens:
        return True
    user_count = count_user_messages_for_trigger(messages)
    return user_count >= fallback_user_message_count


def _create_goal_langfuse_callback():
    """Create Langfuse callback handler for goal agent tracing."""
    goal_pk = app_config.LANGFUSE_PUBLIC_GOAL_KEY
    goal_sk = app_config.LANGFUSE_SECRET_GOAL_KEY
    goal_host = app_config.LANGFUSE_HOST

    if goal_pk and goal_sk and goal_host:
        try:
            callback = CallbackHandler(public_key=goal_pk)
            logger.info("[Langfuse][supervisor] Goal agent callback handler created successfully")
            return callback
        except Exception as e:
            logger.warning("[Langfuse][supervisor] Failed to create goal callback handler: %s: %s", type(e).__name__, e)
            return None
    else:
        logger.warning("[Langfuse][supervisor] Goal agent Langfuse env vars missing; tracing disabled")
        return None


def compile_supervisor_graph(checkpointer=None) -> CompiledStateGraph:
    assign_to_finance_agent_with_description = create_task_description_handoff_tool(
        agent_name="finance_agent",
        description="Assign task to a finance agent for account and transaction queries.",
        destination_agent_name="finance_router",
        tool_name="transfer_to_finance_agent",
        guidelines="""
            Answer exactly the financial metric(s) requested; no extra metrics unless asked.
            Use one well-structured SQL statement to compute the result; avoid probes/pre-checks (SELECT 1/COUNT/EXISTS).
            Minimize tool calls; the database is fast but tool invocations are expensive.
            If the metric is computed, return immediately; do NOT run supplemental queries (count/first/last).
            State the timeframe used; keep the response concise.
        """,
    )
    assign_to_finance_capture_agent_with_description = create_task_description_handoff_tool(
        agent_name="finance_capture_agent",
        description="Assign task to the finance capture agent for collecting user financial data.",
        guidelines="""
            Determine whether the user is adding an asset, liability, or manual transaction.
            Collect structured fields and resolve missing information with focused follow-ups.
            Map Vera categories while selecting Plaid category and subcategory from allowed options.
            Present a concise human confirmation summary before any persistence.
            Persist via the appropriate internal endpoint and report completion details back to the supervisor.
        """,
    )
    assign_to_goal_agent_with_description = create_task_description_handoff_tool(
        agent_name="goal_agent",
        description="Assign task to the goal agent for financial objectives.",
        guidelines="""
            Focus on gathering and analyzing the requested data
            Provide comprehensive analysis with insights
            Return your findings clearly and completely
            Your supervisor will handle the final user-facing response
        """,
    )
    assign_to_wealth_agent_with_description = create_task_description_handoff_tool(
        agent_name="wealth_agent",
        description="Assign task to a wealth agent for Vera app usage questions AND financial education topics.",
        destination_agent_name="wealth_router",
        tool_name="transfer_to_wealth_agent",
        guidelines="""
            Focus on gathering and analyzing the requested data
            Provide comprehensive analysis with insights
            Return your findings clearly and completely
            Your supervisor will handle the final user-facing response
        """,
    )

    if checkpointer is None:
        checkpointer = get_supervisor_checkpointer()

    chat_bedrock = SafeChatCerebras(
        model="gpt-oss-120b",
        api_key=app_config.CEREBRAS_API_KEY,
        temperature=app_config.SUPERVISOR_AGENT_TEMPERATURE or 0.4,
        input_config={
            "use_llm_classifier": True,
            "llm_confidence_threshold": 0.7,
            "enabled_checks": ["injection", "pii", "blocked_topics", "internal_exposure"],
        },
        output_config={
            "use_llm_classifier": False,
            "enabled_checks": ["pii_leakage", "context_exposure", "internal_exposure"],
        },
        user_context={
            "blocked_topics": [],
        },
        fail_open=True,
    )

    summary_max_tokens_default = int(app_config.SUMMARY_MAX_SUMMARY_TOKENS)

    if app_config.SUMMARY_MODEL_ID:
        guardrail_config: dict[str, str] | None = None
        if app_config.SUMMARY_GUARDRAIL_ID and app_config.SUMMARY_GUARDRAIL_VERSION:
            guardrail_config = {
                "guardrailIdentifier": app_config.SUMMARY_GUARDRAIL_ID,
                "guardrailVersion": app_config.SUMMARY_GUARDRAIL_VERSION,
            }

        summarize_model = ChatBedrockConverse(
            model=app_config.SUMMARY_MODEL_ID,
            region_name=app_config.SUMMARY_MODEL_REGION or app_config.get_aws_region(),
            temperature=0.0,
            guardrail_config=guardrail_config,
        )
    else:
        summarize_model = chat_bedrock
    try:
        summarize_model = summarize_model.bind(max_tokens=summary_max_tokens_default)
    except Exception as exc:
        logger.info("summary.model.bind.skip err=%s", exc)

    from app.services.llm.prompt_loader import prompt_loader
    supervisor_prompt = prompt_loader.load("supervisor_system_prompt")

    supervisor_agent_with_description = create_supervisor_subgraph(
        chat_bedrock,
        [
            assign_to_finance_agent_with_description,
            assign_to_finance_capture_agent_with_description,
            assign_to_wealth_agent_with_description,
            assign_to_goal_agent_with_description,
        ],
        supervisor_prompt,
    )

    class SupervisorState(MessagesState):
        context: dict[str, Any]
        navigation_events: list[dict[str, Any]] | None

    builder = StateGraph(SupervisorState)

    summarizer = ConversationSummarizer(
        model=summarize_model,
        summary_max_tokens=summary_max_tokens_default,
        tail_token_budget=int(app_config.SUMMARY_TAIL_TOKEN_BUDGET),
    )

    # --- Routing and memory nodes ---
    builder.add_node("summarize", summarizer.as_node())
    builder.add_node("memory_hotpath", memory_hotpath)
    builder.add_node("memory_context", memory_context)

    # --- Main supervisor node and destinations ---
    builder.add_node(
        "supervisor",
        supervisor_agent_with_description,
        destinations=("finance_agent", "finance_capture_agent", "goal_agent"),
    )

    # --- Specialist agent nodes ---
    builder.add_node("finance_router", finance_router)
    from .finance_agent.agent import finance_agent as finance_worker
    from .finance_capture_agent.subgraph import create_finance_capture_graph
    from .workers import wealth_router

    finance_capture_graph = create_finance_capture_graph(checkpointer)

    builder.add_node("finance_agent", finance_worker)
    builder.add_node("finance_capture_agent", finance_capture_graph)
    builder.add_node("wealth_router", wealth_router)
    builder.add_node("goal_agent", goal_agent)

    # --- Define edges between nodes ---

    def _route_after_start(state: dict[str, Any]) -> str:
        messages = state.get("messages") or []
        context = state.get("context") or {}

        last_prompt_tokens = _coerce_int(context.get(CONTEXT_KEY_MAX_PROMPT_TOKENS_LAST_RUN), 0)
        user_count = count_user_messages_for_trigger(messages)
        reason: str | None = None
        trigger_prompt_tokens = int(app_config.SUMMARY_TRIGGER_PROMPT_TOKEN_COUNT)
        fallback_user_message_count = int(app_config.SUMMARY_TRIGGER_USER_MESSAGE_COUNT_FALLBACK)
        if last_prompt_tokens >= trigger_prompt_tokens:
            reason = SUMMARY_TRIGGER_REASON_PROMPT_TOKENS
        elif user_count >= fallback_user_message_count:
            reason = SUMMARY_TRIGGER_REASON_USER_COUNT_FALLBACK

        should_run_summary = should_trigger_summarization_at_turn_start(
            messages=messages,
            context=context,
            trigger_prompt_tokens=trigger_prompt_tokens,
            fallback_user_message_count=fallback_user_message_count,
        )
        if should_run_summary:
            logger.info(
                "summary.triggered reason=%s thread_id=%s last_prompt_tokens=%s trigger_prompt_tokens=%s user_messages=%s fallback_user_messages=%s",
                reason,
                context.get("thread_id"),
                last_prompt_tokens,
                trigger_prompt_tokens,
                user_count,
                fallback_user_message_count,
            )
        return "summarize" if should_run_summary else "memory_hotpath"

    builder.add_conditional_edges(
        START,
        _route_after_start,
        {
            "summarize": "summarize",
            "memory_hotpath": "memory_hotpath",
        },
    )
    builder.add_edge("summarize", "memory_hotpath")
    builder.add_edge("memory_hotpath", "memory_context")
    builder.add_edge("memory_context", "supervisor")
    builder.add_edge("finance_router", "supervisor")
    builder.add_edge("finance_agent", "supervisor")
    builder.add_edge("finance_capture_agent", "supervisor")
    builder.add_edge("wealth_router", "supervisor")
    builder.add_edge("goal_agent", "supervisor")
    store = create_s3_vectors_store_from_env()
    return builder.compile(store=store, checkpointer=checkpointer)
