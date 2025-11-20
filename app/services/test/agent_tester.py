import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from langchain_aws import ChatBedrockConverse

from app.core.app_state import get_bedrock_runtime_client
from app.core.config import config
from app.services.llm.bedrock import BedrockLLM

logger = logging.getLogger(__name__)


class AgentTester:
    def __init__(self):
        self.agent_methods = {
            "guest": self._test_guest,
            "onboarding": self._test_onboarding,
            "supervisor": self._test_supervisor,
            "wealth": self._test_wealth,
            "goal": self._test_goal,
            "finance": self._test_finance,
            "finance_capture": self._test_finance_capture,
        }

    async def test_agent(self, agent: str, query: Optional[str] = None) -> Dict[str, Any]:
        start_time = time.perf_counter()
        model_id, region = self._get_agent_config(agent)

        if not query:
            query = "Hello World"

        logger.info(f"Testing {agent} agent with query: {query[:50]}...")

        try:
            if agent not in self.agent_methods:
                raise ValueError(f"Agent '{agent}' not found")

            test_method = self.agent_methods[agent]
            response = await test_method(query, model_id, region)
            end_time = time.perf_counter()
            execution_time_seconds = end_time - start_time

            return {
                "success": True,
                "agent": agent,
                "model_id": model_id,
                "region": region,
                "response_message": response,
                "execution_time_seconds": round(execution_time_seconds, 3),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": None,
            }
        except Exception as e:
            end_time = time.perf_counter()
            execution_time_seconds = end_time - start_time

            return {
                "success": False,
                "agent": agent,
                "model_id": model_id,
                "region": region,
                "response_message": None,
                "execution_time_seconds": round(execution_time_seconds, 3),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": str(e),
            }

    def _get_agent_config(self, agent: str) -> tuple[Optional[str], Optional[str]]:
        config_map = {
            "guest": (config.GUEST_AGENT_MODEL_ID, config.GUEST_AGENT_MODEL_REGION),
            "onboarding": (config.ONBOARDING_AGENT_MODEL_ID, config.ONBOARDING_AGENT_MODEL_REGION),
            "supervisor": (config.SUPERVISOR_AGENT_MODEL_ID, config.SUPERVISOR_AGENT_MODEL_REGION),
            "wealth": (config.WEALTH_AGENT_MODEL_ID, config.WEALTH_AGENT_MODEL_REGION),
            "goal": (config.GOAL_AGENT_MODEL_ID, config.GOAL_AGENT_MODEL_REGION),
            "finance": (config.FINANCIAL_AGENT_MODEL_ID, config.FINANCIAL_AGENT_MODEL_REGION),
            "finance_capture": (config.MEMORY_TINY_LLM_MODEL_ID, config.get_aws_region()),
        }
        return config_map.get(agent, (None, None))

    def _parse_content(self, response) -> str:
        content = response.content
        if isinstance(content, list):
            return " ".join(str(item) for item in content)
        return str(content)

    def _get_guardrail_config(self, guardrail_id: Optional[str], guardrail_version: Optional[str]) -> Optional[Dict[str, str]]:
        if guardrail_id and guardrail_version:
            return {
                "guardrailIdentifier": guardrail_id,
                "guardrailVersion": guardrail_version,
            }
        return None

    async def _test_guest(self, query: str, model_id: Optional[str], region: Optional[str]) -> str:
        if not model_id or not region:
            raise ValueError("Guest agent configuration missing: model_id or region not set")

        llm = ChatBedrockConverse(model_id=model_id, region_name=region)
        response = await llm.ainvoke(query)
        return self._parse_content(response)

    async def _test_onboarding(self, query: str, model_id: Optional[str], region: Optional[str]) -> str:
        if not model_id or not region:
            raise ValueError("Onboarding agent configuration missing: model_id or region not set")

        llm = BedrockLLM()
        response = await llm.agenerate(query)
        return response

    async def _test_supervisor(self, query: str, model_id: Optional[str], region: Optional[str]) -> str:
        if not model_id or not region:
            raise ValueError("Supervisor agent configuration missing: model_id or region not set")

        guardrail_config = self._get_guardrail_config(
            config.SUPERVISOR_AGENT_GUARDRAIL_ID, config.SUPERVISOR_AGENT_GUARDRAIL_VERSION
        )

        llm = ChatBedrockConverse(model_id=model_id, region_name=region, guardrail_config=guardrail_config)
        response = await llm.ainvoke(query)
        return self._parse_content(response)

    async def _test_wealth(self, query: str, model_id: Optional[str], region: Optional[str]) -> str:
        if not model_id or not region:
            raise ValueError("Wealth agent configuration missing: model_id or region not set")

        guardrail_config = self._get_guardrail_config(
            config.WEALTH_AGENT_GUARDRAIL_ID, config.WEALTH_AGENT_GUARDRAIL_VERSION
        )

        llm = ChatBedrockConverse(model_id=model_id, region_name=region, guardrail_config=guardrail_config)
        response = await llm.ainvoke(query)
        return self._parse_content(response)

    async def _test_goal(self, query: str, model_id: Optional[str], region: Optional[str]) -> str:

        if not model_id or not region:
            raise ValueError("Goal agent configuration missing: model_id or region not set")

        llm_params = {"model_id": model_id, "region_name": region, "provider": config.GOAL_AGENT_PROVIDER}
        llm = ChatBedrockConverse(**llm_params)
        response = await llm.ainvoke(query)
        return self._parse_content(response)

    async def _test_finance(self, query: str, model_id: Optional[str], region: Optional[str]) -> str:
        if not model_id or not region:
            raise ValueError("Finance agent configuration missing: model_id or region not set")

        guardrail_config = self._get_guardrail_config(
            config.FINANCIAL_AGENT_GUARDRAIL_ID, config.FINANCIAL_AGENT_GUARDRAIL_VERSION
        )

        llm = ChatBedrockConverse(model_id=model_id, region_name=region, guardrail_config=guardrail_config)
        response = await llm.ainvoke(query)
        return self._parse_content(response)

    async def _test_finance_capture(self, query: str, model_id: Optional[str], region: Optional[str]) -> str:
        if not model_id or not region:
            raise ValueError("Finance capture agent configuration missing: model_id or region not set")

        bedrock_runtime = get_bedrock_runtime_client()
        response = bedrock_runtime.converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": query}]}],
        )
        return response["output"]["message"]["content"][0]["text"]
