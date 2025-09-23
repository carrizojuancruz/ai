from pydantic import BaseModel, Field


class TitleGenerationRequest(BaseModel):
    """Request model for title generation."""

    body: str = Field(..., description="Content body to generate title and summary from")


class TitleGenerationResponse(BaseModel):
    """Response model for title generation."""

    title: str = Field(..., description="Generated title for the content")
    summary: str = Field(..., max_length=125, description="Generated summary up to 125 characters")
