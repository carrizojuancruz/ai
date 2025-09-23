from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.api.schemas.title_gen import TitleGenerationRequest, TitleGenerationResponse
from app.services.llm.title_generator import TitleGeneratorLLM

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/title-gen", tags=["Title Generation"])

# Initialize the title generator service
title_generator = TitleGeneratorLLM()


@router.post("/generate", response_model=TitleGenerationResponse)
async def generate_title_and_summary(request: TitleGenerationRequest) -> TitleGenerationResponse:
    """Generate title and summary for Pin content."""
    try:
        logger.info(f"Generating title and summary for content with {len(request.body)} characters")

        if not request.body.strip():
            raise HTTPException(status_code=400, detail="Content body cannot be empty")

        if len(request.body) > 10000:  # Reasonable limit for content size
            raise HTTPException(status_code=400, detail="Content body too large (max 10,000 characters)")

        result = await title_generator.generate_title_and_summary(request.body)

        logger.info("Successfully generated title and summary")

        return TitleGenerationResponse(
            title=result["title"],
            summary=result["summary"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate title and summary: {e}")
        raise HTTPException(status_code=500, detail="Internal server error generating title and summary") from e
