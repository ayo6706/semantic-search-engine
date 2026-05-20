import asyncio

import pytest
from unittest.mock import AsyncMock, patch

import app.api.v1.endpoints.search as search_endpoint
from app.api.v1.endpoints.search import search
from app.schemas.search import SearchRequest, SearchMode, ScoredChunk, SearchResponse
from app.integrations.llm.litellm import LiteLLMProvider
from app.integrations.vectorstores.chroma import ChromaDBVectorStore
from app.search.pipeline import SearchPipeline
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.search.SearchCacheService")
@patch("app.api.v1.endpoints.search.get_redis_client")
@patch("app.api.v1.endpoints.search.get_cross_encoder")
@patch("app.api.v1.endpoints.search.build_pipeline")
@patch("app.api.v1.endpoints.search.DocumentRepository")
async def test_search_response_includes_latency_and_metadata(
    mock_doc_repo_class,
    mock_build_pipeline,
    mock_get_cross_encoder,
    mock_get_redis,
    mock_cache_class,
):
    # Mock cache to miss
    mock_cache = AsyncMock()
    mock_cache.get.return_value = None
    mock_cache_class.return_value = mock_cache
    
    # Mock pipeline to return a dummy chunk
    mock_pipeline = AsyncMock(spec=SearchPipeline)
    mock_pipeline.execute.return_value = [
        ScoredChunk(id="c1", doc_id="d1", text="some test text here", page_num=1, dense_score=0.9, sparse_score=0.5, rerank_score=0.95)
    ]
    mock_build_pipeline.return_value = mock_pipeline
    
    # Mock DocumentRepository batch resolution
    mock_repo = AsyncMock()
    mock_repo.get_filenames_by_ids.return_value = {"d1": "test_doc.pdf"}
    mock_doc_repo_class.return_value = mock_repo
    
    # Dependencies
    request = SearchRequest(query="test", search_mode=SearchMode.HYBRID, top_k=10, use_reranker=True)
    session = AsyncMock(spec=AsyncSession)
    llm = AsyncMock(spec=LiteLLMProvider)
    vs = AsyncMock(spec=ChromaDBVectorStore)
    cross_encoder = object()
    mock_get_cross_encoder.return_value = cross_encoder
    
    response = await search(request, session, llm, vs)
    
    assert response.query == "test"
    assert response.total_results == 1
    assert response.search_mode == SearchMode.HYBRID.value
    assert response.reranker_used is True
    assert isinstance(response.latency_ms, float)
    
    result = response.results[0]
    assert result.chunk_id == "c1"
    assert result.doc_id == "d1"
    assert result.doc_filename == "test_doc.pdf"
    assert result.dense_score == 0.9
    assert result.sparse_score == 0.5
    assert result.rerank_score == 0.95
    assert result.score == 0.95  # final score defaults to rerank_score if present
    assert "<mark>test</mark>" in result.snippet
    mock_get_cross_encoder.assert_awaited_once()
    mock_build_pipeline.assert_called_once()
    assert mock_build_pipeline.call_args.kwargs["cross_encoder"] is cross_encoder


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.search.SearchCacheService")
@patch("app.api.v1.endpoints.search.get_redis_client")
@patch("app.api.v1.endpoints.search.get_cross_encoder")
@patch("app.api.v1.endpoints.search.build_pipeline")
async def test_search_cache_hit_skips_pipeline_and_cross_encoder(
    mock_build_pipeline,
    mock_get_cross_encoder,
    mock_get_redis,
    mock_cache_class,
):
    cached_response = SearchResponse(
        results=[],
        query="test",
        total_results=0,
        latency_ms=12.3,
        search_mode="hybrid",
        reranker_used=True,
    )
    mock_cache = AsyncMock()
    mock_cache.get.return_value = cached_response
    mock_cache_class.return_value = mock_cache

    request = SearchRequest(query="test", search_mode=SearchMode.HYBRID, use_reranker=True)
    session = AsyncMock(spec=AsyncSession)
    llm = AsyncMock(spec=LiteLLMProvider)
    vs = AsyncMock(spec=ChromaDBVectorStore)

    response = await search(request, session, llm, vs)

    assert response is cached_response
    mock_get_cross_encoder.assert_not_awaited()
    mock_build_pipeline.assert_not_called()
    mock_cache.set.assert_not_awaited()


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.search.SearchCacheService")
@patch("app.api.v1.endpoints.search.get_redis_client")
@patch("app.api.v1.endpoints.search.get_cross_encoder")
@patch("app.api.v1.endpoints.search.build_pipeline")
@patch("app.api.v1.endpoints.search.DocumentRepository")
async def test_search_without_reranker_does_not_load_cross_encoder(
    mock_doc_repo_class,
    mock_build_pipeline,
    mock_get_cross_encoder,
    mock_get_redis,
    mock_cache_class,
):
    mock_cache = AsyncMock()
    mock_cache.get.return_value = None
    mock_cache_class.return_value = mock_cache

    mock_pipeline = AsyncMock(spec=SearchPipeline)
    mock_pipeline.execute.return_value = []
    mock_build_pipeline.return_value = mock_pipeline

    mock_repo = AsyncMock()
    mock_repo.get_filenames_by_ids.return_value = {}
    mock_doc_repo_class.return_value = mock_repo

    request = SearchRequest(query="test", search_mode=SearchMode.DENSE, use_reranker=False)
    session = AsyncMock(spec=AsyncSession)
    llm = AsyncMock(spec=LiteLLMProvider)
    vs = AsyncMock(spec=ChromaDBVectorStore)

    response = await search(request, session, llm, vs)

    assert response.reranker_used is False
    mock_get_cross_encoder.assert_not_awaited()
    mock_build_pipeline.assert_called_once()
    assert mock_build_pipeline.call_args.kwargs["cross_encoder"] is None


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.search.SearchCacheService")
@patch("app.api.v1.endpoints.search.get_redis_client")
@patch("app.api.v1.endpoints.search.get_cross_encoder")
@patch("app.api.v1.endpoints.search.build_pipeline")
@patch("app.api.v1.endpoints.search.DocumentRepository")
async def test_search_falls_back_when_reranker_fails_to_load(
    mock_doc_repo_class,
    mock_build_pipeline,
    mock_get_cross_encoder,
    mock_get_redis,
    mock_cache_class,
):
    mock_cache = AsyncMock()
    mock_cache.get.return_value = None
    mock_cache_class.return_value = mock_cache

    mock_get_cross_encoder.side_effect = RuntimeError("model load failed")

    mock_pipeline = AsyncMock(spec=SearchPipeline)
    mock_pipeline.execute.return_value = [
        ScoredChunk(
            id="c1",
            doc_id="d1",
            text="some test text here",
            page_num=1,
            dense_score=0.9,
        )
    ]
    mock_build_pipeline.return_value = mock_pipeline

    mock_repo = AsyncMock()
    mock_repo.get_filenames_by_ids.return_value = {"d1": "test_doc.pdf"}
    mock_doc_repo_class.return_value = mock_repo

    request = SearchRequest(
        query="test",
        search_mode=SearchMode.HYBRID,
        top_k=10,
        use_reranker=True,
    )
    session = AsyncMock(spec=AsyncSession)
    llm = AsyncMock(spec=LiteLLMProvider)
    vs = AsyncMock(spec=ChromaDBVectorStore)

    response = await search(request, session, llm, vs)

    assert response.reranker_used is False
    assert response.total_results == 1
    mock_get_cross_encoder.assert_awaited_once()
    mock_build_pipeline.assert_called_once()
    assert mock_build_pipeline.call_args.kwargs["cross_encoder"] is None
    assert mock_build_pipeline.call_args.kwargs["use_reranker"] is False
    mock_cache.set.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_cross_encoder_initializes_once_for_concurrent_requests(monkeypatch):
    created = []

    class FakeCrossEncoder:
        def __init__(self):
            created.append(self)

    monkeypatch.setattr(search_endpoint, "_cross_encoder", None)
    monkeypatch.setattr(search_endpoint, "_cross_encoder_lock", asyncio.Lock())
    monkeypatch.setattr(search_endpoint, "CrossEncoderReranker", FakeCrossEncoder)

    first, second = await asyncio.gather(
        search_endpoint.get_cross_encoder(),
        search_endpoint.get_cross_encoder(),
    )

    assert first is second
    assert created == [first]
