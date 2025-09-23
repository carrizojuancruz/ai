from __future__ import annotations

import datetime
import logging
from typing import Any, Optional
from uuid import UUID

from langchain_aws import ChatBedrockConverse
from langchain_core.messages import HumanMessage
from langgraph.graph import MessagesState
from langgraph.types import Command, RunnableConfig

from app.agents.supervisor.finance_agent.helpers import (
    create_error_command,
    extract_text_from_content,
    get_last_user_message_text,
    get_user_id_from_messages,
    rows_to_json,
    serialize_sample_row,
)
from app.agents.supervisor.finance_agent.prompts import build_finance_system_prompt
from app.agents.supervisor.finance_agent.subgraph import create_finance_subgraph
from app.agents.supervisor.finance_agent.tools import create_sql_db_query_tool
from app.agents.supervisor.handoff import create_handoff_back_messages
from app.core.app_state import (
    get_cached_finance_agent,
    get_finance_agent,
    get_finance_samples,
    set_cached_finance_agent,
    set_finance_samples,
)
from app.core.config import config
from app.repositories.database_service import get_database_service
from app.repositories.postgres.finance_repository import FinanceTables
from app.utils.tools import get_config_value

logger = logging.getLogger(__name__)


def _extract_text_from_content(content) -> str:
    return extract_text_from_content(content)


def _get_last_user_message_text(messages: list[HumanMessage | dict[str, Any]]) -> str:
    return get_last_user_message_text(messages)


def _get_user_id_from_messages(messages: list[HumanMessage | dict[str, Any]]) -> Optional[UUID]:
    return get_user_id_from_messages(messages)


def _create_error_command(error_message: str) -> Command:
    return create_error_command(error_message)


class FinanceAgent:
    """Finance agent for querying Plaid financial data using tools."""

    SAMPLE_CACHE_TTL_SECONDS: int = 600
    MAX_TRANSACTION_SAMPLES: int = 2
    MAX_ACCOUNT_SAMPLES: int = 1

    def __init__(self):
        logger.info("Initializing FinanceAgent with Bedrock models")

        guardrails = {
            "guardrailIdentifier": config.FINANCIAL_AGENT_GUARDRAIL_ID,
            "guardrailVersion": config.FINANCIAL_AGENT_GUARDRAIL_VERSION,
            "trace": "enabled",
        }

        self.sql_generator = ChatBedrockConverse(
            model_id=config.FINANCIAL_AGENT_MODEL_ID,
            region_name=config.FINANCIAL_AGENT_MODEL_REGION,
            temperature=config.FINANCIAL_AGENT_TEMPERATURE,
            guardrail_config=guardrails,
        )

        logger.info("FinanceAgent initialization completed")
        self._sample_cache: dict[str, dict[str, Any]] = {}

    async def _fetch_shallow_samples(self, user_id: UUID) -> tuple[str, str]:
        """Fetch sample data for transactions and accounts.

        Returns compact JSON arrays as strings for embedding in the prompt.
        """
        try:
            cached_pair = get_finance_samples(user_id)
            if cached_pair:
                return cached_pair

            now = datetime.datetime.utcnow().timestamp()
            cache_key = str(user_id)
            cached = self._sample_cache.get(cache_key)
            if cached and (now - cached.get("cached_at", 0) < self.SAMPLE_CACHE_TTL_SECONDS):
                return cached.get("tx_samples", "[]"), cached.get("acct_samples", "[]")

            db_service = get_database_service()
            async with db_service.get_session() as session:
                repo = db_service.get_finance_repository(session)

                tx_query = (
                    "SELECT "
                    "  t.external_transaction_id AS dedupe_id, "
                    "  t.amount, "
                    "  COALESCE(t.transaction_date::date, t.authorized_date::date) AS tx_date, "
                    "  COALESCE(NULLIF(t.merchant_name,''), NULLIF(t.name,'')) AS merchant, "
                    "  COALESCE(t.provider_tx_category_detailed, t.category_detailed, t.provider_tx_category, t.category, 'Uncategorized') AS category, "
                    "  t.pending, "
                    "  t.created_at "
                    f"FROM {FinanceTables.TRANSACTIONS} t "
                    "WHERE t.user_id = :user_id "
                    f"ORDER BY t.created_at DESC LIMIT {self.MAX_TRANSACTION_SAMPLES}"
                )

                acct_query = (
                    "SELECT a.id, a.name, a.account_type, a.account_subtype, a.institution_name, a.created_at "
                    f"FROM {FinanceTables.ACCOUNTS} a "
                    "WHERE a.user_id = :user_id "
                    f"ORDER BY a.created_at DESC LIMIT {self.MAX_ACCOUNT_SAMPLES}"
                )

                tx_rows = await repo.execute_query(tx_query, user_id=str(user_id))
                acct_rows = await repo.execute_query(acct_query, user_id=str(user_id))

                tx_rows_serialized = [serialize_sample_row(r) for r in (tx_rows or [])]
                acct_rows_serialized = [serialize_sample_row(r) for r in (acct_rows or [])]

                tx_json = rows_to_json(tx_rows_serialized)
                acct_json = rows_to_json(acct_rows_serialized)

                self._sample_cache[cache_key] = {
                    "tx_samples": tx_json,
                    "acct_samples": acct_json,
                    "cached_at": now,
                }
                from contextlib import suppress

                with suppress(Exception):
                    set_finance_samples(user_id, tx_json, acct_json)
                return tx_json, acct_json
        except Exception as e:
            logger.warning(f"Error fetching samples: {e}")
            return "[]", "[]"

    def _serialize_sample_row(self, row) -> dict[str, Any]:
        return serialize_sample_row(row)

    def _rows_to_json(self, rows: list[dict[str, Any]]) -> str:
        """Convert serialized rows to JSON string."""
        import json

        return json.dumps(rows, ensure_ascii=False, separators=(",", ":"))

    async def _create_system_prompt(self, user_id: UUID) -> str:
        tx_samples, acct_samples = await self._fetch_shallow_samples(user_id)

        return await build_finance_system_prompt(user_id, tx_samples, acct_samples)

    async def _create_agent_with_tools(self, user_id: UUID):
        logger.info(f"Creating financial agent for user {user_id}")

        tools = [create_sql_db_query_tool(user_id)]

        async def prompt_builder() -> str:
            return await self._create_system_prompt(user_id)


        return create_finance_subgraph(self.sql_generator, tools, prompt_builder)


    async def process_query_with_agent(self, query: str, user_id: UUID) -> Command:
        """Process financial queries and return the Command from agent execution."""
        try:
            logger.info(f"Processing finance query with agent for user {user_id}: {query}")

            agent = get_cached_finance_agent(user_id)
            if agent is None:
                agent = await self._create_agent_with_tools(user_id)
                set_cached_finance_agent(user_id, agent)
            else:
                logger.info(f"Using cached LangGraph agent for user {user_id}")

            messages = [HumanMessage(content=query)]

            logger.info(f"Starting LangGraph agent execution for user {user_id}")
            agent_command = await agent.ainvoke({"messages": messages}, config={"recursion_limit": 10})
            logger.info(f"Agent execution completed for user {user_id}")

            return agent_command

        except Exception as e:
            logger.error(f"Finance agent error for user {user_id}: {e}")
            return _create_error_command("I encountered an error while processing your financial query. Please try again.")


async def finance_agent(state: MessagesState, config: RunnableConfig) -> Command:
    """LangGraph node for finance agent that provides analysis to supervisor."""
    try:
        user_id = get_config_value(config, "user_id")
        if not user_id:
            user_id = _get_user_id_from_messages(state["messages"])

        query = _get_last_user_message_text(state["messages"])
        logger.info(f"Finance agent - user_id: {user_id}, task: {query[:100]}...")

        if not user_id:
            logger.warning("No user_id found in finance agent request")
            return _create_error_command("ERROR: Cannot access financial data without user identification.")

        if not query:
            logger.warning("No task description found in finance agent request")
            return _create_error_command("ERROR: No task description provided for analysis.")

        finance_agent_instance = get_finance_agent()
        agent_command = await finance_agent_instance.process_query_with_agent(query, user_id)

        return agent_command

    except Exception as e:
        logger.error(f"Finance agent critical error: {e}")
        error_analysis = f"FINANCIAL ANALYSIS ERROR: {str(e)}"

        handoff_messages = create_handoff_back_messages("finance_agent", "supervisor")

        return Command(
            update={
                "messages": [
                    {"role": "assistant", "content": error_analysis, "name": "finance_agent"},
                    handoff_messages[0]
                ]
            },
            goto="supervisor"
        )
