import asyncio
import time
from types import SimpleNamespace
import uuid

import pydantic
import pytest

from app.repositories.chunk import ChunkRepository
from app.schemas.search import ScoredChunk, SearchMode, SearchRequest
from app.search.fusers.noop import NoopFuser
from app.search.fusers.rrf import RRFFuser
from app.search.factory import build_pipeline
from app.search.pipeline import SearchPipeline, SearchPipelineCancelled
from app.search.rerankers.cross_encoder import CrossEncoderReranker
from app.search.rerankers.noop import NoopReranker
from app.search.retrievers.dense import DenseRetriever
from app.search.snippet import extract_snippet
from app.search.types import StaleChecker


def test_scored_chunk_final_score():
    chunk = ScoredChunk(id="1", doc_id="d1", text="test", page_num=1)
    assert chunk.final_score == 0.0

    chunk.sparse_score = 1.5
    assert chunk.final_score == 1.5

    chunk.dense_score = 0.8
    assert chunk.final_score == 0.8

    chunk.fused_score = 0.02
    assert chunk.final_score == 0.02

    chunk.rerank_score = 0.95
    assert chunk.final_score == 0.95


def test_rrf_fuser():
    dense = [
        ScoredChunk(id="c1", doc_id="d1", text="text1", page_num=1, dense_score=0.9),
        ScoredChunk(id="c2", doc_id="d1", text="text2", page_num=1, dense_score=0.8),
        ScoredChunk(id="c3", doc_id="d2", text="text3", page_num=1, dense_score=0.7),
    ]
    sparse = [
        ScoredChunk(id="c2", doc_id="d1", text="text2", page_num=1, sparse_score=2.5),
        ScoredChunk(id="c1", doc_id="d1", text="text1", page_num=1, sparse_score=1.5),
        ScoredChunk(id="c4", doc_id="d2", text="text4", page_num=1, sparse_score=0.5),
    ]

    fuser = RRFFuser(k=60)
    fused = fuser.fuse([dense, sparse])

    assert len(fused) == 4

    # Verify RRF merges both scores onto the exact same chunk ID

    c1_fused = next(c for c in fused if c.id == "c1")
    c2_fused = next(c for c in fused if c.id == "c2")
    c3_fused = next(c for c in fused if c.id == "c3")
    c4_fused = next(c for c in fused if c.id == "c4")

    assert c1_fused.dense_score == 0.9
    assert c1_fused.sparse_score == 1.5

    assert c2_fused.dense_score == 0.8
    assert c2_fused.sparse_score == 2.5

    assert c3_fused.dense_score == 0.7
    assert c3_fused.sparse_score is None

    assert c4_fused.sparse_score == 0.5
    assert c4_fused.dense_score is None

    expected_c1 = (1.0 / (60 + 0 + 1)) + (1.0 / (60 + 1 + 1))
    assert abs(c1_fused.fused_score - expected_c1) < 1e-6


@pytest.mark.asyncio
async def test_noop_fuser_and_reranker():
    chunks = [
        ScoredChunk(id="c1", doc_id="d1", text="text1", page_num=1, dense_score=0.9),
        ScoredChunk(id="c2", doc_id="d1", text="text2", page_num=1, dense_score=0.8),
    ]

    fuser = NoopFuser()
    fused = fuser.fuse([chunks, []])
    assert fused == chunks

    reranker = NoopReranker()
    reranked = await reranker.rerank("query", chunks, top_n=1)
    assert len(reranked) == 1
    assert reranked[0].id == "c1"


def test_extract_snippet():
    text = "This is the first sentence. Here is the second sentence containing the keyword. This is the third sentence without it. And a fourth one."
    query = "keyword"

    snippet = extract_snippet(text, query, max_sentences=2)
    assert "<mark>keyword</mark>" in snippet
    assert "second sentence" in snippet

    text2 = "Some UPPERCASE Keyword here."
    snippet2 = extract_snippet(text2, "keyword")
    assert "<mark>Keyword</mark>" in snippet2


def test_extract_snippet_uses_whole_word_overlap():
    text = (
        "Partial matches like cart and artist are unrelated. "
        "Exact art appears here."
    )

    snippet = extract_snippet(text, "art", max_sentences=1)

    assert "Partial matches" not in snippet
    assert "Exact <mark>art</mark>" in snippet


def test_extract_snippet_highlights_once_without_rewriting_markup():
    snippet = extract_snippet("The mark token is here.", "mark")

    assert snippet.count("<mark>") == 1
    assert snippet.count("</mark>") == 1
    assert "<mark>mark</mark>" in snippet


def test_extract_snippet_adds_trailing_ellipsis_after_mid_text_snippet():
    text = "First sentence. Matching term is here. Final sentence."

    snippet = extract_snippet(text, "term", max_sentences=1)

    assert snippet.startswith("... ")
    assert snippet.endswith(" ...")


def test_extract_snippet_ellipsis_uses_window_indices_for_duplicate_sentences():
    text = "Repeat sentence. Unique keyword appears. Repeat sentence."

    snippet = extract_snippet(text, "keyword", max_sentences=1)

    assert snippet == "... Unique <mark>keyword</mark> appears. ..."


@pytest.mark.asyncio
async def test_pipeline_limits_rerank_candidate_window(monkeypatch):
    chunks = [
        ScoredChunk(id=f"c{i}", doc_id="d1", text=f"text {i}", page_num=1)
        for i in range(10)
    ]

    class FakeRetriever:
        async def retrieve(self, query, top_k=50, doc_ids=None):
            return chunks

    class FakeFuser:
        def fuse(self, result_sets):
            return result_sets[0]

    class RecordingReranker:
        def __init__(self):
            self.received_count = 0
            self.top_n = 0

        async def rerank(
            self,
            query,
            chunks,
            top_n=10,
            is_stale: StaleChecker | None = None,
        ):
            self.received_count = len(chunks)
            self.top_n = top_n
            return chunks[:top_n]

    reranker = RecordingReranker()
    monkeypatch.setattr("app.search.pipeline.search_settings.RERANK_TOP_N", 3)

    pipeline = SearchPipeline([FakeRetriever()], FakeFuser(), reranker)
    results = await pipeline.execute("query", top_k=2)

    assert len(results) == 2
    assert reranker.received_count == 3
    assert reranker.top_n == 2


@pytest.mark.asyncio
async def test_pipeline_skips_reranking_when_request_becomes_stale():
    chunks = [ScoredChunk(id="c1", doc_id="d1", text="text", page_num=1)]

    class FakeRetriever:
        async def retrieve(self, query, top_k=50, doc_ids=None):
            return chunks

    class FakeFuser:
        def fuse(self, result_sets):
            return result_sets[0]

    class RecordingReranker:
        called = False

        async def rerank(
            self,
            query,
            chunks,
            top_n=10,
            is_stale: StaleChecker | None = None,
        ):
            self.called = True
            return chunks

    reranker = RecordingReranker()
    pipeline = SearchPipeline([FakeRetriever()], FakeFuser(), reranker)

    async def is_stale():
        return True

    with pytest.raises(SearchPipelineCancelled):
        await pipeline.execute("query", is_stale=is_stale)

    assert reranker.called is False


def test_build_pipeline_allows_missing_cross_encoder_when_reranker_disabled():
    pipeline = build_pipeline(
        search_mode=SearchMode.DENSE,
        use_reranker=False,
        llm_provider=object(),
        vector_store=object(),
        session=object(),
    )

    assert isinstance(pipeline.reranker, NoopReranker)


def test_build_pipeline_requires_cross_encoder_when_reranker_enabled():
    with pytest.raises(ValueError, match="cross_encoder is required"):
        build_pipeline(
            search_mode=SearchMode.DENSE,
            use_reranker=True,
            llm_provider=object(),
            vector_store=object(),
            session=object(),
        )


def test_search_request_validation():
    with pytest.raises(pydantic.ValidationError):
        SearchRequest(query="   ")

    with pytest.raises(pydantic.ValidationError):
        SearchRequest(query="valid", top_k=0)

    with pytest.raises(pydantic.ValidationError):
        SearchRequest(query="valid", doc_ids=[])


@pytest.mark.asyncio
async def test_full_text_search_converts_doc_ids_to_uuid_params():
    doc_id = uuid.uuid4()
    chunk_id = uuid.uuid4()

    class FakeSession:
        def __init__(self):
            self.params = None

        async def execute(self, stmt, params):
            self.params = params
            return [
                SimpleNamespace(
                    id=chunk_id,
                    doc_id=doc_id,
                    text="matching text",
                    page_number=1,
                    rank=0.5,
                )
            ]

    session = FakeSession()
    repo = ChunkRepository(session)

    results = await repo.full_text_search("matching", doc_ids=[str(doc_id)])

    assert session.params["doc_ids"] == [doc_id]
    assert results == [
        {
            "id": str(chunk_id),
            "doc_id": str(doc_id),
            "text": "matching text",
            "page_number": 1,
            "rank": 0.5,
        }
    ]


@pytest.mark.asyncio
async def test_full_text_search_reports_invalid_doc_id():
    repo = ChunkRepository(SimpleNamespace())

    with pytest.raises(ValueError, match="doc_ids must contain valid UUID strings"):
        await repo.full_text_search("matching", doc_ids=["not-a-uuid"])


@pytest.mark.asyncio
async def test_dense_retriever_reports_missing_metadata_key():
    class FakeLLMProvider:
        async def embed_text(self, query):
            return [0.1]

    class FakeVectorStore:
        async def query(self, embedding, top_k=50, doc_ids=None):
            return {
                "ids": [["chunk-1"]],
                "distances": [[0.1]],
                "documents": [["text"]],
                "metadatas": [[{"doc_id": "doc-1"}]],
            }

    retriever = DenseRetriever(FakeLLMProvider(), FakeVectorStore())

    with pytest.raises(ValueError, match="page_number"):
        await retriever.retrieve("query")


@pytest.mark.asyncio
async def test_cross_encoder_reranker_does_not_mutate_input_order(monkeypatch):
    class FakeCrossEncoder:
        def __init__(self, model_name, **kwargs):
            pass

        def predict(self, pairs):
            return [0.2, 0.9]

    monkeypatch.setattr(
        "app.search.rerankers.cross_encoder.CrossEncoder",
        FakeCrossEncoder,
    )

    reranker = CrossEncoderReranker()
    chunks = [
        ScoredChunk(id="c1", doc_id="d1", text="first", page_num=1),
        ScoredChunk(id="c2", doc_id="d1", text="second", page_num=1),
    ]

    reranked = await reranker.rerank("query", chunks, top_n=2)

    assert [chunk.id for chunk in chunks] == ["c1", "c2"]
    assert [chunk.id for chunk in reranked] == ["c2", "c1"]


@pytest.mark.asyncio
async def test_cross_encoder_reranker_serializes_predict_calls(monkeypatch):
    class FakeCrossEncoder:
        active_calls = 0
        max_active_calls = 0

        def __init__(self, model_name, **kwargs):
            pass

        def predict(self, pairs):
            type(self).active_calls += 1
            type(self).max_active_calls = max(
                type(self).max_active_calls,
                type(self).active_calls,
            )
            time.sleep(0.01)
            type(self).active_calls -= 1
            return [0.5 for _ in pairs]

    monkeypatch.setattr(
        "app.search.rerankers.cross_encoder.CrossEncoder",
        FakeCrossEncoder,
    )

    reranker = CrossEncoderReranker()
    chunks = [ScoredChunk(id="c1", doc_id="d1", text="first", page_num=1)]

    await asyncio.gather(
        reranker.rerank("query", chunks),
        reranker.rerank("query", chunks),
    )

    assert FakeCrossEncoder.max_active_calls == 1


@pytest.mark.asyncio
async def test_cross_encoder_reranker_skips_stale_request_after_queue(monkeypatch):
    predict_calls = 0

    class FakeCrossEncoder:
        def __init__(self, model_name, **kwargs):
            pass

        def predict(self, pairs):
            nonlocal predict_calls
            predict_calls += 1
            time.sleep(0.02)
            return [0.5 for _ in pairs]

    monkeypatch.setattr(
        "app.search.rerankers.cross_encoder.CrossEncoder",
        FakeCrossEncoder,
    )

    reranker = CrossEncoderReranker()
    chunks = [ScoredChunk(id="c1", doc_id="d1", text="first", page_num=1)]
    stale = False

    first_result_task = asyncio.create_task(reranker.rerank("query", chunks))
    await asyncio.sleep(0)

    async def is_second_stale():
        return stale

    second_result_task = asyncio.create_task(
        reranker.rerank("query", chunks, is_stale=is_second_stale)
    )
    await asyncio.sleep(0.005)
    stale = True

    first_result = await first_result_task
    second_result = await second_result_task

    assert len(first_result) == 1
    assert second_result == []
    assert predict_calls == 1


def test_cross_encoder_reranker_uses_cache_only_loading(monkeypatch):
    created = {}

    class FakeCrossEncoder:
        def __init__(self, model_name, **kwargs):
            created["model_name"] = model_name
            created.update(kwargs)

    monkeypatch.setattr(
        "app.search.rerankers.cross_encoder.CrossEncoder",
        FakeCrossEncoder,
    )

    CrossEncoderReranker(
        model_name="model-id",
        cache_folder="/models/huggingface",
        local_files_only=True,
    )

    assert created == {
        "model_name": "model-id",
        "cache_folder": "/models/huggingface",
        "local_files_only": True,
    }
