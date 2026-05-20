from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field, field_validator


class SearchMode(str, Enum):
    """Available search modes."""
    DENSE = "dense"
    SPARSE = "sparse"
    HYBRID = "hybrid"


@dataclass
class ScoredChunk:
    """A chunk of text scored by one or more retrievers/fusers.
    
    This is a lightweight mutable dataclass rather than a Pydantic model
    to avoid overhead during pipeline execution.
    """
    id: str
    doc_id: str
    text: str
    page_num: int
    dense_score: float | None = None
    sparse_score: float | None = None
    fused_score: float | None = None
    rerank_score: float | None = None

    @property
    def final_score(self) -> float:
        """Get the most relevant score available."""
        if self.rerank_score is not None:
            return self.rerank_score
        if self.fused_score is not None:
            return self.fused_score
        if self.dense_score is not None:
            return self.dense_score
        if self.sparse_score is not None:
            return self.sparse_score
        return 0.0


class SearchRequest(BaseModel):
    """Search request parameters."""
    query: str = Field(..., min_length=1)
    doc_ids: list[str] | None = None
    top_k: int = Field(default=10, gt=0)
    use_reranker: bool = True
    search_mode: SearchMode = SearchMode.HYBRID

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must not be blank.")
        return value

    @field_validator("doc_ids")
    @classmethod
    def doc_ids_must_not_be_empty(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and not value:
            raise ValueError("doc_ids must be omitted or contain at least one ID.")
        return value


class SearchResult(BaseModel):
    """A single highlighted search result."""
    model_config = ConfigDict(from_attributes=True)

    chunk_id: str
    doc_id: str
    doc_filename: str
    page_num: int
    snippet: str
    text: str
    score: float
    dense_score: float | None = None
    sparse_score: float | None = None
    rerank_score: float | None = None


class SearchResponse(BaseModel):
    """Complete search response."""
    results: list[SearchResult]
    query: str
    total_results: int
    latency_ms: float
    search_mode: str
    reranker_used: bool
