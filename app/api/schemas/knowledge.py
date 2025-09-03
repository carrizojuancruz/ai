from pydantic import BaseModel


class SearchRequest(BaseModel):
    query: str
    limit: int = 5


class SearchResponse(BaseModel):
    results: list
    query: str
    total_results: int
