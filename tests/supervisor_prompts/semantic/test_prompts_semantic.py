from __future__ import annotations

import os
from pathlib import Path

import pytest
from langchain.evaluation import load_evaluator
from langchain_aws import ChatBedrock

from app.core.config import config
from tests.supervisor_prompts.loader import PromptSpec, load_prompt, load_specs

SPEC_PATH = Path(__file__).parent.parent / "prompt_specs.json"
DEFAULT_INSTRUCTIONS = [
    "Judge whether this prompt enforces the described behavior and safety requirements.",
    "Confirm it clearly communicates the agent's role, limitations, and required output format.",
]


def _build_bedrock_model() -> ChatBedrock:
    model_id = os.getenv("PROMPT_EVAL_MODEL_ID") or config.SUPERVISOR_AGENT_MODEL_ID
    region = (
        os.getenv("PROMPT_EVAL_MODEL_REGION")
        or config.SUPERVISOR_AGENT_MODEL_REGION
        or config.AWS_REGION
    )
    if not model_id or not region:
        pytest.skip("Bedrock model id or region not configured for prompt evaluation")
    temperature = float(os.getenv("PROMPT_EVAL_TEMPERATURE", "0.0"))
    return ChatBedrock(model_id=model_id, region_name=region, temperature=temperature)


@pytest.fixture(scope="session")
def bedrock_evaluator():
    llm = _build_bedrock_model()
    return load_evaluator("criteria", llm=llm)


@pytest.fixture(scope="session")
def prompt_specs() -> list[PromptSpec]:
    return load_specs(SPEC_PATH)


@pytest.mark.parametrize("spec", [pytest.param(s, id=s.name) for s in load_specs(SPEC_PATH)])
def test_prompt_with_llm_judge(spec: PromptSpec, bedrock_evaluator) -> None:
    prompt_text = load_prompt(spec)
    instructions = (spec.evaluation or {}).get("instructions", DEFAULT_INSTRUCTIONS)
    rubric = "\n".join(instructions)
    result = bedrock_evaluator.evaluate_strings(
        prediction=prompt_text,
        input=rubric,
    )
    score = float(result.get("score", 0.0))
    assert score >= 0.7, f"LLM judge flagged prompt {spec.name}: {result}"
