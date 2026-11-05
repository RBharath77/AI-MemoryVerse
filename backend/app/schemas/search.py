from pydantic import BaseModel, ConfigDict, Field


class HybridSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=10, ge=1, le=50)
    include_documents: bool = True
    include_memories: bool = True
    filter_category: str | None = None


class SearchResultResponseItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source_type: str
    id: str
    title: str
    content: str
    score: float
    category: str | None = None
    section_title: str | None = None
    metadata: dict = {}


class HybridSearchResponse(BaseModel):
    query: str
    results: list[SearchResultResponseItem]
    total_found: int
