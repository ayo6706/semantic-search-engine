import pytest
import redis.asyncio as redis
from unittest.mock import AsyncMock

from app.schemas.search import SearchRequest, SearchMode, SearchResponse, SearchResult
from app.services.cache import _build_cache_key, SearchCacheService

def test_cache_key_determinism():
    req1 = SearchRequest(query="test", search_mode=SearchMode.HYBRID, top_k=10, use_reranker=True)
    req2 = SearchRequest(query="test", search_mode=SearchMode.HYBRID, top_k=10, use_reranker=True)
    assert _build_cache_key(req1) == _build_cache_key(req2)

def test_cache_key_varies_with_params():
    req_base = SearchRequest(query="test", search_mode=SearchMode.HYBRID, top_k=10, use_reranker=True)
    req_query = SearchRequest(query="test2", search_mode=SearchMode.HYBRID, top_k=10, use_reranker=True)
    req_mode = SearchRequest(query="test", search_mode=SearchMode.DENSE, top_k=10, use_reranker=True)
    req_top_k = SearchRequest(query="test", search_mode=SearchMode.HYBRID, top_k=5, use_reranker=True)
    req_rerank = SearchRequest(query="test", search_mode=SearchMode.HYBRID, top_k=10, use_reranker=False)

    base_key = _build_cache_key(req_base)
    assert base_key != _build_cache_key(req_query)
    assert base_key != _build_cache_key(req_mode)
    assert base_key != _build_cache_key(req_top_k)
    assert base_key != _build_cache_key(req_rerank)

@pytest.mark.asyncio
async def test_cache_get_returns_none_on_miss():
    mock_redis = AsyncMock(spec=redis.Redis)
    mock_redis.get = AsyncMock(return_value=None)
    
    cache = SearchCacheService(mock_redis)
    req = SearchRequest(query="test")
    assert await cache.get(req) is None

@pytest.mark.asyncio
async def test_cache_get_returns_stored_response():
    req = SearchRequest(query="test")
    resp = SearchResponse(
        results=[
            SearchResult(
                chunk_id="c1", doc_id="d1", doc_filename="test.pdf", page_num=1,
                snippet="test", text="test", score=1.0
            )
        ],
        query="test",
        total_results=1,
        latency_ms=10.0,
        search_mode="hybrid",
        reranker_used=True,
    )
    
    mock_redis = AsyncMock(spec=redis.Redis)
    mock_redis.get = AsyncMock(return_value=resp.model_dump_json())
    
    cache = SearchCacheService(mock_redis)
    retrieved = await cache.get(req)
    
    assert retrieved is not None
    assert retrieved.query == "test"
    assert retrieved.total_results == 1
    assert retrieved.latency_ms == 10.0

@pytest.mark.asyncio
async def test_cache_graceful_degradation():
    mock_redis = AsyncMock(spec=redis.Redis)
    mock_redis.get = AsyncMock(side_effect=Exception("Redis connection failed"))
    
    cache = SearchCacheService(mock_redis)
    req = SearchRequest(query="test")
    
    # Should not raise
    assert await cache.get(req) is None

@pytest.mark.asyncio
async def test_invalidate_all_deletes_search_keys():
    mock_redis = AsyncMock(spec=redis.Redis)

    class FakePipeline:
        def __init__(self):
            self.keys = []

        def delete(self, *keys):
            self.keys.extend(keys)

        async def execute(self):
            return [len(self.keys)]

    pipeline = FakePipeline()
    mock_redis.pipeline.return_value = pipeline
    
    async def mock_scan_iter(match=None, count=None):
        yield "search:123"
        yield "search:456"
        
    mock_redis.scan_iter = mock_scan_iter
    
    cache = SearchCacheService(mock_redis)
    await cache.invalidate_all()

    mock_redis.pipeline.assert_called_once_with(transaction=False)
    assert pipeline.keys == ["search:123", "search:456"]
