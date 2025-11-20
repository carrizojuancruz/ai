import logging

from fastapi import APIRouter, HTTPException

from app.api.schemas.test_schemas import AgentTestRequest, AgentTestResponse
from app.services.test.agent_tester import AgentTester

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/test", tags=["Testing"])


@router.post(
    "/agent",
    response_model=AgentTestResponse,
    summary="Test Agent Performance",
    description="""
    Test agent performance and scalability by invoking the underlying LLM.

    **Available Agents:**
    - `guest` - Guest/unauthenticated user agent
    - `onboarding` - User onboarding agent
    - `supervisor` - Main supervisor/orchestrator agent
    - `wealth` - Wealth management agent
    - `goal` - Financial goal planning agent
    - `finance` - Financial analysis agent
    - `finance_capture` - Transaction capture agent

    **Returns:** Model configuration, response message, and execution time.
    """,
    responses={
        200: {"description": "Agent test successful"},
        404: {"description": "Agent not found"},
        500: {"description": "Agent execution error"},
        503: {"description": "Agent configuration missing"},
        504: {"description": "Request timeout"}
    }
)
async def test_agent_endpoint(request: AgentTestRequest):
    logger.info(f"Testing agent: {request.agent} with query: {request.query[:50] if request.query else 'default'}")

    tester = AgentTester()
    result = await tester.test_agent(request.agent.value, request.query)

    if not result["success"]:
        error_msg = result.get("error", "").lower()
        if "not found" in error_msg or "not supported" in error_msg:
            raise HTTPException(status_code=404, detail=result["error"])
        elif "timeout" in error_msg:
            raise HTTPException(status_code=504, detail=result["error"])
        elif "config" in error_msg or "not set" in error_msg or "missing" in error_msg:
            raise HTTPException(status_code=503, detail=result["error"])
        else:
            raise HTTPException(status_code=500, detail=result["error"])

    logger.info(f"Agent test completed: {request.agent} - status 200 - {result['execution_time_seconds']:.3f}s")
    return AgentTestResponse(**result)
