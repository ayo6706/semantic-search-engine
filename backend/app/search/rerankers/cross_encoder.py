import asyncio
import logging
import time

from sentence_transformers import CrossEncoder

from app.core.config import search_settings
from app.schemas.search import ScoredChunk
from app.search.rerankers.base import BaseReranker


logger = logging.getLogger(__name__)


class CrossEncoderReranker(BaseReranker):
    """Reranker using a HuggingFace cross-encoder model.
    
    Loads the model once at initialization. Model evaluation is run
    in a separate thread to avoid blocking the asyncio event loop.
    """

    def __init__(
        self,
        model_name: str | None = None,
        cache_folder: str | None = None,
        local_files_only: bool | None = None,
    ):
        self._predict_lock = asyncio.Lock()
        model_name = model_name or search_settings.RERANKER_MODEL
        cache_folder = cache_folder or search_settings.RERANKER_CACHE_DIR
        if local_files_only is None:
            local_files_only = search_settings.RERANKER_LOCAL_FILES_ONLY

        attempts = 3
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                logger.info("Loading cross-encoder model: %s", model_name)
                self.model = CrossEncoder(
                    model_name,
                    cache_folder=cache_folder,
                    local_files_only=local_files_only,
                )
                return
            except Exception as exc:
                last_error = exc
                logger.error(
                    "Failed to load cross-encoder model %s on attempt %d/%d: %s",
                    model_name,
                    attempt,
                    attempts,
                    exc,
                    exc_info=True,
                )
                if attempt < attempts:
                    time.sleep(attempt)

        raise RuntimeError(
            f"Failed to load cross-encoder model {model_name!r} after "
            f"{attempts} attempts."
        ) from last_error

    async def rerank(
        self,
        query: str,
        chunks: list[ScoredChunk],
        top_n: int = 10
    ) -> list[ScoredChunk]:
        """Rerank chunks using the cross-encoder model."""
        if not chunks:
            return []

        # Prepare pairs for the cross-encoder: (query, document_text)
        pairs = [[query, chunk.text] for chunk in chunks]

        start_time = time.perf_counter()

        # Run inference in a thread pool so it doesn't block the async event loop
        async with self._predict_lock:
            scores = await asyncio.to_thread(self.model.predict, pairs)
        
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        if elapsed_ms > 500:
            logger.warning(f"Cross-encoder reranking took {elapsed_ms:.1f}ms (>500ms) for {len(chunks)} chunks")

        # Update scores on chunks
        for i, chunk in enumerate(chunks):
            # scores is a numpy array, convert to standard float
            chunk.rerank_score = float(scores[i])

        # Sort descending by the new rerank_score without mutating caller order.
        sorted_chunks = sorted(chunks, key=lambda x: x.rerank_score, reverse=True)

        return sorted_chunks[:top_n]
