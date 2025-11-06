from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from langchain_aws import ChatBedrockConverse
from langchain_core.messages import BaseMessage
from langchain_core.messages.utils import count_tokens_approximately
from langfuse.langchain import CallbackHandler
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import RunnableConfig
from langmem.short_term import RunningSummary

from app.agents.supervisor.memory import episodic_capture, memory_context, memory_hotpath
from app.agents.supervisor.summarizer import ConversationSummarizer
from app.core.config import config as app_config
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

TRACE_STAGE_RESTORED = "restored"
TRACE_STAGE_AFTER_SUMMARIZE = "after_summarize"
TRACE_STAGE_AFTER_HOTPATH = "after_memory_hotpath"
TRACE_STAGE_AFTER_CONTEXT = "after_memory_context"

SUMMARY_MAX_SUMMARY_TOKENS_DEFAULT: int | None = app_config.SUMMARY_MAX_SUMMARY_TOKENS
SUMMARY_TAIL_TOKEN_BUDGET_DEFAULT: int | None = app_config.SUMMARY_TAIL_TOKEN_BUDGET


def log_state_snapshot(
    stage: str,
    messages: Iterable[BaseMessage],
    context: dict[str, Any],
    token_counter: Callable[[Sequence[BaseMessage]], int],
) -> None:
    if not app_config.SUPERVISOR_TRACE_ENABLED:
        return
    try:
        message_list = [message for message in messages if isinstance(message, BaseMessage)]
        serialized_messages = [serialize_message(message) for message in message_list]
        token_count = token_counter(message_list)
        record: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stage": stage,
            "token_count": token_count,
            "message_count": len(serialized_messages),
            "messages": serialized_messages,
        }
        running_summary = context.get("running_summary") if isinstance(context, dict) else None
        serialized_summary = serialize_running_summary(running_summary)
        if serialized_summary is not None:
            record["running_summary"] = serialized_summary
        append_trace_record(record)
    except Exception as exc:
        logger.warning("supervisor.trace.write_failed err=%s", exc)


def append_trace_record(record: dict[str, Any]) -> None:
    path = Path(app_config.SUPERVISOR_TRACE_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False))
        handle.write("\n")


def serialize_message(message: BaseMessage) -> dict[str, Any]:
    if hasattr(message, "to_json"):
        try:
            data = message.to_json()
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {
        "type": getattr(message, "type", "unknown"),
        "content": getattr(message, "content", None),
        "additional_kwargs": getattr(message, "additional_kwargs", {}),
        "response_metadata": getattr(message, "response_metadata", {}),
        "tool_calls": getattr(message, "tool_calls", []),
    }


def serialize_running_summary(running_summary: RunningSummary | None) -> dict[str, Any] | None:
    if running_summary is None:
        return None
    return {
        "summary": running_summary.summary,
        "summarized_message_ids": sorted(running_summary.summarized_message_ids),
        "last_summarized_message_id": running_summary.last_summarized_message_id,
    }


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

    guardrails = {
        "guardrailIdentifier": app_config.SUPERVISOR_AGENT_GUARDRAIL_ID,
        "guardrailVersion": app_config.SUPERVISOR_AGENT_GUARDRAIL_VERSION,
        "trace": "enabled",
    }

    if checkpointer is None:
        checkpointer = get_supervisor_checkpointer()

    chat_bedrock = ChatBedrockConverse(
        model_id=app_config.SUPERVISOR_AGENT_MODEL_ID,
        region_name=app_config.SUPERVISOR_AGENT_MODEL_REGION,
        temperature=app_config.SUPERVISOR_AGENT_TEMPERATURE,
        guardrail_config=guardrails,
        additional_model_request_fields={"reasoning_effort": app_config.SUPERVISOR_AGENT_REASONING_EFFORT},
    )

    if app_config.SUMMARY_MODEL_ID:
        summarize_model = ChatBedrockConverse(
            model_id=app_config.SUMMARY_MODEL_ID,
            region_name=app_config.SUPERVISOR_AGENT_MODEL_REGION,
            temperature=0.0,
        )
    else:
        summarize_model = chat_bedrock
    # Enforce summary length if supported by the model
    try:
        summarize_model = summarize_model.bind(max_tokens=SUMMARY_MAX_SUMMARY_TOKENS_DEFAULT)
        logger.info("summary.model.bind max_tokens=%d", SUMMARY_MAX_SUMMARY_TOKENS_DEFAULT)
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
        context: dict[str, RunningSummary]
        total_tokens: int
        navigation_events: list[dict[str, Any]] | None

    builder = StateGraph(SupervisorState)

    def count_tokens(messages: Sequence[BaseMessage]) -> int:
        # Fallback to approximate counting; accumulation handled at call time
        try:
            return chat_bedrock.get_num_tokens_from_messages(messages)
        except Exception:
            return count_tokens_approximately(messages)

    def make_snapshot_node(stage: str) -> Callable[[SupervisorState], dict[str, Any]]:
        def snapshot(state: SupervisorState) -> dict[str, Any]:
            log_state_snapshot(
                stage,
                state.get("messages") or [],
                state.get("context", {}),
                count_tokens,
            )
            return {}

        return snapshot

    def update_visible_tokens(state: SupervisorState, run_config: RunnableConfig | None = None) -> dict[str, Any]:
        """Compute token count of current visible state messages for gating."""
        total = count_tokens(state.get("messages") or [])
        ctx = state.get("context", {}) or {}
        ctx["state_visible_tokens"] = total
        return {"context": ctx}

    summarizer = ConversationSummarizer(
        model=summarize_model,
        token_counter=count_tokens,
        tail_token_budget=SUMMARY_TAIL_TOKEN_BUDGET_DEFAULT,
        summary_max_tokens=SUMMARY_MAX_SUMMARY_TOKENS_DEFAULT,
    )

    # --- Memory and context nodes ---
    builder.add_node("snapshot_restore", make_snapshot_node(TRACE_STAGE_RESTORED))
    builder.add_node("summarize", summarizer.as_node())

    def _to_plain_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        # Bedrock/Anthropic may return list of blocks
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
                    except Exception:
                        pass
            return "\n".join([p for p in parts if p])
        # Objects with .content
        content = getattr(value, "content", None)
        if isinstance(content, str):
            return content
        return str(value)

    def post_summarize_tokens(state: SupervisorState, run_config: RunnableConfig | None = None) -> dict[str, Any]:
        """After summarization, recompute visible tokens for downstream nodes."""
        ctx = state.get("context", {}) or {}
        total = count_tokens(state.get("messages") or [])
        ctx["state_visible_tokens"] = total
        return {"context": ctx}

    builder.add_node("post_summarize_tokens", post_summarize_tokens)
    builder.add_node("update_visible_tokens", update_visible_tokens)
    builder.add_node("memory_hotpath", memory_hotpath)
    builder.add_node("memory_context", memory_context)

    def should_summarize(state: SupervisorState, run_config: RunnableConfig | None = None) -> dict[str, Any]:
        ctx = state.get("context", {}) or {}
        total = int(ctx.get("state_visible_tokens", 0))
        threshold = app_config.SUMMARY_MAX_TOKENS_BEFORE
        if threshold is None:
            logger.warning("SUMMARY_MAX_TOKENS_BEFORE not set, skipping summarization")
            return {"should_summarize": False}
        decision = total >= threshold
        logger.info("summ.gate visible_tokens=%d threshold=%d decision=%s", total, threshold, decision)
        return {"should_summarize": decision}

    builder.add_node("should_summarize", should_summarize)

    # --- Main supervisor node and destinations ---
    builder.add_node(
        "supervisor",
        supervisor_agent_with_description,
        destinations=("finance_agent", "finance_capture_agent", "goal_agent", "episodic_capture"),
    )

    # --- Specialist agent nodes ---
    builder.add_node("episodic_capture", episodic_capture)
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
    builder.add_edge(START, "snapshot_restore")
    builder.add_edge("snapshot_restore", "update_visible_tokens")
    builder.add_edge("update_visible_tokens", "should_summarize")
    builder.add_conditional_edges(
        "should_summarize",
        lambda s: "summarize" if s.get("should_summarize") else "skip",
        {"summarize": "summarize", "skip": "memory_hotpath"},
    )
    builder.add_edge("summarize", "post_summarize_tokens")
    builder.add_edge("post_summarize_tokens", "memory_hotpath")
    builder.add_edge("memory_hotpath", "memory_context")
    builder.add_edge("memory_context", "supervisor")
    builder.add_edge("finance_router", "supervisor")
    builder.add_edge("finance_agent", "supervisor")
    builder.add_edge("finance_capture_agent", "supervisor")
    builder.add_edge("wealth_router", "supervisor")
    builder.add_edge("goal_agent", "supervisor")
    store = create_s3_vectors_store_from_env()
    return builder.compile(store=store, checkpointer=checkpointer)
