import json
import logging
from typing import Optional
from uuid import UUID

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import MessagesState

from app.core.app_state import get_bedrock_runtime_client
from app.core.config import config
from app.services.nudges.icebreaker_processor import get_icebreaker_processor
from app.utils.tools import get_config_value

logger = logging.getLogger(__name__)


async def _create_natural_icebreaker(icebreaker_text: str, user_id: UUID) -> Optional[str]:
    try:
        logger.debug(f"icebreaker_consumer.llm_starting: user_id={user_id}, input_text={icebreaker_text[:100]}...")

        bedrock = get_bedrock_runtime_client()
        model_id = config.MEMORY_TINY_LLM_MODEL_ID

        prompt = f"""Create a warm, natural conversation starter based on this memory:

Memory: {icebreaker_text}

Requirements:
- Sound like a friendly, personal assistant (Vera)
- Use "you" instead of third person (e.g., "you enjoy hiking" not "Rick enjoys hiking")
- Make it conversational and engaging
- Keep it 1-2 sentences
- Don't mention "memories" or "I remember" - just reference it naturally
- Use a warm, encouraging tone

Examples:
- Memory: "Rick enjoys hiking in Golden Gate Park"
- Good: "I noticed you love hiking in Golden Gate Park! How's that been going lately?"
- Bad: "This came up in my memories: Rick enjoys hiking in Golden Gate Park."

Memory: {icebreaker_text}
Natural icebreaker:"""

        body_payload = {
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {"temperature": 0.7, "topP": 0.9, "maxTokens": 100, "stopSequences": []},
        }

        logger.debug(f"icebreaker_consumer.llm_calling: user_id={user_id}, model_id={model_id}")
        response = bedrock.invoke_model(modelId=model_id, body=json.dumps(body_payload))
        body = response.get("body")
        raw_text = body.read().decode("utf-8") if hasattr(body, "read") else str(body)
        data = json.loads(raw_text)

        generated_text = ""
        try:
            contents = data.get("output", {}).get("message", {}).get("content", "")
            if isinstance(contents, list):
                for part in contents:
                    if isinstance(part, dict) and part.get("text"):
                        generated_text += part.get("text", "")
            elif isinstance(contents, str):
                generated_text = contents
        except Exception:
            generated_text = data.get("outputText") or data.get("generation") or ""

        if not generated_text or not generated_text.strip():
            logger.warning(f"icebreaker_consumer.llm_no_output: user_id={user_id}")
            return None

        generated_text = generated_text.strip()

        logger.info(f"icebreaker_consumer.llm_success: user_id={user_id}, generated={generated_text[:100]}...")

        return generated_text

    except Exception as e:
        logger.error(f"icebreaker_consumer.llm_error: user_id={user_id}, error={str(e)}")
        return None


async def debug_icebreaker_flow(user_id: str) -> dict:
    try:
        from uuid import UUID

        user_uuid = UUID(user_id)

        logger.info(f"debug_icebreaker_flow.start: user_id={user_uuid}")

        from app.core.app_state import get_fos_nudge_manager

        fos_manager = get_fos_nudge_manager()

        logger.info(f"debug_icebreaker_flow.fos_manager: available={fos_manager is not None}")

        icebreakers = await fos_manager.get_pending_nudges(user_uuid, nudge_type="memory_icebreaker", limit=100)
        logger.info(f"debug_icebreaker_flow.icebreakers: count={len(icebreakers)}")

        user_icebreakers = [n for n in icebreakers if n.user_id == str(user_uuid)]
        logger.info(f"debug_icebreaker_flow.user_icebreakers: count={len(user_icebreakers)}")

        if user_icebreakers:
            best = user_icebreakers[0]
            logger.info(f"debug_icebreaker_flow.best_nudge: id={best.message_id}, priority={best.priority}")
            logger.info(f"debug_icebreaker_flow.best_payload: {best.nudge_payload}")

        return {
            "icebreakers": len(icebreakers),
            "user_icebreakers": len(user_icebreakers),
            "best_nudge": user_icebreakers[0].message_id if user_icebreakers else None,
        }

    except Exception as e:
        logger.error(f"debug_icebreaker_flow.error: {str(e)}", exc_info=True)
        return {"error": str(e)}


async def icebreaker_consumer(state: MessagesState, config: RunnableConfig) -> dict:
    user_id = None
    try:
        user_id = get_config_value(config, "user_id")
        if not user_id:
            logger.debug("icebreaker_consumer.no_user_id: skipping icebreaker consumption")
            return {}

        if isinstance(user_id, str):
            user_id = UUID(user_id)

        logger.info(f"icebreaker_consumer.starting: user_id={user_id}")

        try:
            processor = get_icebreaker_processor()
            logger.debug(f"icebreaker_consumer.processor_created: user_id={user_id}")
        except Exception as e:
            logger.error(f"icebreaker_consumer.processor_error: user_id={user_id}, error={str(e)}")
            return {}

        try:
            icebreaker_text = await processor.process_icebreaker_for_user(user_id)
            logger.debug(f"icebreaker_consumer.processed: user_id={user_id}, has_text={bool(icebreaker_text)}")
        except Exception as e:
            logger.error(f"icebreaker_consumer.process_error: user_id={user_id}, error={str(e)}")
            return {}

        if not icebreaker_text:
            logger.info(f"icebreaker_consumer.no_icebreaker: user_id={user_id}, continuing normally")
            return {}

        logger.info(f"icebreaker_consumer.found_icebreaker: user_id={user_id}, raw_text={icebreaker_text[:100]}...")

        try:
            icebreaker_context = await _create_natural_icebreaker(icebreaker_text, user_id)
            logger.debug(
                f"icebreaker_consumer.llm_processed: user_id={user_id}, has_context={bool(icebreaker_context)}"
            )
        except Exception as e:
            logger.error(f"icebreaker_consumer.llm_error: user_id={user_id}, error={str(e)}")
            return {}

        if not icebreaker_context:
            logger.warning(f"icebreaker_consumer.llm_failed: user_id={user_id}, continuing without icebreaker")
            return {}

        context_message = HumanMessage(content=f"ICEBREAKER_CONTEXT: {icebreaker_context}", name="icebreaker_system")

        messages = state.get("messages", [])
        messages.insert(0, context_message)

        logger.info(
            f"icebreaker_consumer.injected: user_id={user_id}, "
            f"context_preview={icebreaker_context[:100]}..., total_messages={len(messages)}"
        )

        return {"messages": messages}

    except Exception as e:
        logger.error(
            f"icebreaker_consumer.critical_error: user_id={user_id if user_id else 'unknown'}, error={str(e)}",
            exc_info=True,
        )
        return {}
