import asyncio

import pytest
from unittest.mock import AsyncMock, patch

import app.api.dependencies as api_deps
from app.api.v1.endpoints.search import search
from app.schemas.search import SearchRequest, SearchMode, ScoredChunk, SearchResponse
from app.integrations.llm.litellm import LiteLLMProvider
from app.integrations.vectorstores.chroma import ChromaDBVectorStore
from app.search.cancellation import search_cancellation_registry
from app.search.pipeline import SearchPipeline, SearchPipelineCancelled
from app.services.search import SearchService
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_search_endpoint_delegates_to_service():
    request = SearchRequest(query="test", search_mode=SearchMode.HYBRID)
    expected = SearchResponse(
        results=[],
        query="test",
        total_results=0,
        latency_ms=1.0,
        search_mode="hybrid",
        reranker_used=False,
    )
    service = AsyncMock(spec=SearchService)
    service.search.return_value = expected

    raw_request = AsyncMock()
    raw_request.is_disconnected = AsyncMock(return_value=False)

    response = await search(request, raw_request, service)

    assert response is expected
    service.search.assert_awaited_once_with(
        request,
        is_disconnected=raw_request.is_disconnected,
        is_stale=None,
    )


@pytest.mark.asyncio
async def test_search_endpoint_passes_stale_checker():
    request = SearchRequest(query="test", search_mode=SearchMode.HYBRID)
    expected = SearchResponse(
        results=[],
        query="test",
        total_results=0,
        latency_ms=1.0,
        search_mode="hybrid",
        reranker_used=False,
    )
    service = AsyncMock(spec=SearchService)
    service.search.return_value = expected

    raw_request = AsyncMock()
    raw_request.is_disconnected = AsyncMock(return_value=False)

    response = await search(
        request,
        raw_request,
        service,
        search_session_id="tab-1",
        search_request_id=1,
    )

    assert response is expected
    is_stale = service.search.await_args.kwargs["is_stale"]
    assert await is_stale() is False

    await search_cancellation_registry.mark_latest("tab-1", 2)
    assert await is_stale() is True


@pytest.mark.asyncio
@patch("app.services.search.get_search_cache")
@patch("app.services.search.build_pipeline")
@patch("app.services.search.DocumentRepository")
async def test_search_response_includes_latency_and_metadata(
    mock_doc_repo_class,
    mock_build_pipeline,
    mock_get_search_cache,
):
    mock_cache = AsyncMock()
    mock_cache.get.return_value = None
    mock_get_search_cache.return_value = mock_cache

    mock_pipeline = AsyncMock(spec=SearchPipeline)
    mock_pipeline.execute.return_value = [
        ScoredChunk(id="c1", doc_id="d1", text="some test text here", page_num=1, dense_score=0.9, sparse_score=0.5, rerank_score=0.95)
    ]
    mock_build_pipeline.return_value = mock_pipeline

    mock_repo = AsyncMock()
    mock_repo.get_filenames_by_ids.return_value = {"d1": "test_doc.pdf"}
    mock_doc_repo_class.return_value = mock_repo

    request = SearchRequest(query="test", search_mode=SearchMode.HYBRID, top_k=10, use_reranker=True)
    session = AsyncMock(spec=AsyncSession)
    llm = AsyncMock(spec=LiteLLMProvider)
    vs = AsyncMock(spec=ChromaDBVectorStore)
    cross_encoder = object()
    get_cross_encoder = AsyncMock(return_value=cross_encoder)
    service = SearchService(session, llm, vs, get_cross_encoder)

    response = await service.search(request)
    
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
    assert result.score == 0.95
    assert "<mark>test</mark>" in result.snippet
    get_cross_encoder.assert_awaited_once()
    mock_build_pipeline.assert_called_once()
    assert mock_build_pipeline.call_args.kwargs["cross_encoder"] is cross_encoder


@pytest.mark.asyncio
@patch("app.services.search.get_search_cache")
@patch("app.services.search.build_pipeline")
async def test_search_cache_hit_skips_pipeline_and_cross_encoder(
    mock_build_pipeline,
    mock_get_search_cache,
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
    mock_get_search_cache.return_value = mock_cache

    request = SearchRequest(query="test", search_mode=SearchMode.HYBRID, use_reranker=True)
    session = AsyncMock(spec=AsyncSession)
    llm = AsyncMock(spec=LiteLLMProvider)
    vs = AsyncMock(spec=ChromaDBVectorStore)
    get_cross_encoder = AsyncMock()
    service = SearchService(session, llm, vs, get_cross_encoder)

    response = await service.search(request)

    assert response is cached_response
    get_cross_encoder.assert_not_awaited()
    mock_build_pipeline.assert_not_called()
    mock_cache.set.assert_not_awaited()


@pytest.mark.asyncio
@patch("app.services.search.get_search_cache")
@patch("app.services.search.build_pipeline")
@patch("app.services.search.DocumentRepository")
async def test_stale_search_response_is_not_cached(
    mock_doc_repo_class,
    mock_build_pipeline,
    mock_get_search_cache,
):
    mock_cache = AsyncMock()
    mock_cache.get.return_value = None
    mock_get_search_cache.return_value = mock_cache

    mock_pipeline = AsyncMock(spec=SearchPipeline)
    mock_pipeline.execute.return_value = []
    mock_build_pipeline.return_value = mock_pipeline

    request = SearchRequest(query="test", search_mode=SearchMode.HYBRID)
    session = AsyncMock(spec=AsyncSession)
    llm = AsyncMock(spec=LiteLLMProvider)
    vs = AsyncMock(spec=ChromaDBVectorStore)
    get_cross_encoder = AsyncMock(return_value=object())
    service = SearchService(session, llm, vs, get_cross_encoder)

    async def is_stale():
        return True

    response = await service.search(request, is_stale=is_stale)

    assert response.total_results == 0
    get_cross_encoder.assert_not_awaited()
    mock_build_pipeline.assert_not_called()
    mock_doc_repo_class.assert_not_called()
    mock_cache.set.assert_not_awaited()


@pytest.mark.asyncio
@patch("app.services.search.get_search_cache")
@patch("app.services.search.build_pipeline")
@patch("app.services.search.DocumentRepository")
async def test_disconnected_search_response_is_not_cached(
    mock_doc_repo_class,
    mock_build_pipeline,
    mock_get_search_cache,
):
    mock_cache = AsyncMock()
    mock_cache.get.return_value = None
    mock_get_search_cache.return_value = mock_cache

    mock_pipeline = AsyncMock(spec=SearchPipeline)
    mock_pipeline.execute.side_effect = SearchPipelineCancelled
    mock_build_pipeline.return_value = mock_pipeline

    request = SearchRequest(query="test", search_mode=SearchMode.HYBRID)
    session = AsyncMock(spec=AsyncSession)
    llm = AsyncMock(spec=LiteLLMProvider)
    vs = AsyncMock(spec=ChromaDBVectorStore)
    get_cross_encoder = AsyncMock(return_value=object())
    service = SearchService(session, llm, vs, get_cross_encoder)

    response = await service.search(request)

    assert response.total_results == 0
    mock_doc_repo_class.assert_not_called()
    mock_cache.set.assert_not_awaited()


@pytest.mark.asyncio
@patch("app.services.search.get_search_cache")
@patch("app.services.search.build_pipeline")
@patch("app.services.search.DocumentRepository")
async def test_search_without_reranker_does_not_load_cross_encoder(
    mock_doc_repo_class,
    mock_build_pipeline,
    mock_get_search_cache,
):
    mock_cache = AsyncMock()
    mock_cache.get.return_value = None
    mock_get_search_cache.return_value = mock_cache

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
    get_cross_encoder = AsyncMock()
    service = SearchService(session, llm, vs, get_cross_encoder)

    response = await service.search(request)

    assert response.reranker_used is False
    get_cross_encoder.assert_not_awaited()
    mock_build_pipeline.assert_called_once()
    assert mock_build_pipeline.call_args.kwargs["cross_encoder"] is None


@pytest.mark.asyncio
@patch("app.services.search.get_search_cache")
@patch("app.services.search.build_pipeline")
@patch("app.services.search.DocumentRepository")
async def test_search_falls_back_when_reranker_fails_to_load(
    mock_doc_repo_class,
    mock_build_pipeline,
    mock_get_search_cache,
):
    mock_cache = AsyncMock()
    mock_cache.get.return_value = None
    mock_get_search_cache.return_value = mock_cache

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
    get_cross_encoder = AsyncMock(side_effect=RuntimeError("model load failed"))
    service = SearchService(session, llm, vs, get_cross_encoder)

    response = await service.search(request)

    assert response.reranker_used is False
    assert response.total_results == 1
    get_cross_encoder.assert_awaited_once()
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

    monkeypatch.setattr(api_deps, "_cross_encoder", None)
    monkeypatch.setattr(api_deps, "_cross_encoder_lock", asyncio.Lock())
    monkeypatch.setattr(api_deps, "CrossEncoderReranker", FakeCrossEncoder)

    first, second = await asyncio.gather(
        api_deps.get_cross_encoder(),
        api_deps.get_cross_encoder(),
    )

    assert first is second
    assert created == [first]


@pytest.mark.asyncio
async def test_get_llm_provider_initializes_once_for_concurrent_requests(monkeypatch):
    created = []

    class FakeLLMProvider:
        def __init__(self):
            created.append(self)

    monkeypatch.setattr(api_deps, "_llm_provider", None)
    monkeypatch.setattr(api_deps, "_llm_provider_lock", asyncio.Lock())
    monkeypatch.setattr(api_deps, "LiteLLMProvider", FakeLLMProvider)

    first, second = await asyncio.gather(
        api_deps.get_llm_provider(),
        api_deps.get_llm_provider(),
    )

    assert first is second
    assert created == [first]


@pytest.mark.asyncio
async def test_get_vector_store_initializes_once_for_concurrent_requests(monkeypatch):
    created = []

    class FakeVectorStore:
        def __init__(self):
            created.append(self)

    monkeypatch.setattr(api_deps, "_vector_store", None)
    monkeypatch.setattr(api_deps, "_vector_store_lock", asyncio.Lock())
    monkeypatch.setattr(api_deps, "ChromaDBVectorStore", FakeVectorStore)

    first, second = await asyncio.gather(
        api_deps.get_vector_store(),
        api_deps.get_vector_store(),
    )

    assert first is second
    assert created == [first]
