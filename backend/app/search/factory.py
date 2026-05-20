from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import search_settings
from app.integrations.llm.base import BaseLLMProvider
from app.integrations.vectorstores.base import BaseVectorStore
from app.schemas.search import SearchMode
from app.search.fusers.noop import NoopFuser
from app.search.fusers.rrf import RRFFuser
from app.search.pipeline import SearchPipeline
from app.search.rerankers.base import BaseReranker
from app.search.rerankers.cross_encoder import CrossEncoderReranker
from app.search.rerankers.noop import NoopReranker
from app.search.retrievers.dense import DenseRetriever
from app.search.retrievers.sparse import SparseRetriever


def build_pipeline(
    search_mode: SearchMode,
    use_reranker: bool,
    llm_provider: BaseLLMProvider,
    vector_store: BaseVectorStore,
    session: AsyncSession,
    cross_encoder: CrossEncoderReranker | None = None,
) -> SearchPipeline:
    """Factory function to build a SearchPipeline instance based on request parameters.
    
    This function configures the strategy pattern components without modifying
    the pipeline's execution logic.
    """
    retrievers = []
    
    if search_mode in (SearchMode.DENSE, SearchMode.HYBRID):
        retrievers.append(DenseRetriever(llm_provider, vector_store))
        
    if search_mode in (SearchMode.SPARSE, SearchMode.HYBRID):
        retrievers.append(SparseRetriever(session))
        
    if not retrievers:
        retrievers.append(DenseRetriever(llm_provider, vector_store))

    fuser = NoopFuser()
    if search_mode == SearchMode.HYBRID:
        fuser = RRFFuser(k=search_settings.RRF_K)

    reranker: BaseReranker = NoopReranker()
    if use_reranker:
        if cross_encoder is None:
            raise ValueError("cross_encoder is required when use_reranker is True.")
        reranker = cross_encoder

    return SearchPipeline(
        retrievers=retrievers,
        fuser=fuser,
        reranker=reranker
    )
