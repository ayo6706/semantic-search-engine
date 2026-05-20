# Retrieval Ablation Evaluation Report

This report summarizes the retrieval accuracy and latency across different configurations of the search pipeline. The evaluation dataset consists of 45 queries (15 keyword, 15 semantic, and 15 hybrid) evaluated against 3 test legal documents.

## Overall Ablation Comparison

| Configuration | MRR | NDCG@10 | Precision@5 | Latency (ms) |
| :--- | :---: | :---: | :---: | :---: |
| Dense Only | 0.9556 | 0.9672 | 0.2000 | 1224.99 ms |
| Sparse Only | 0.3778 | 0.3778 | 0.0756 | 6.48 ms |
| Hybrid RRF | 0.9667 | 0.9754 | 0.2000 | 15.61 ms |
| Hybrid + Rerank | 0.9667 | 0.9754 | 0.2000 | 22.49 ms |
| Hybrid + Rerank (Chunk=256) | 0.7667 | 0.7987 | 0.1778 | 24.16 ms |

## Retrieval Accuracy by Query Type (MRR)

| Configuration | Keyword Queries | Semantic Queries | Hybrid Queries |
| :--- | :---: | :---: | :---: |
| Dense Only | 0.9000 | 0.9821 | 0.9167 |
| Sparse Only | 0.6000 | 0.3214 | 0.4167 |
| Hybrid RRF | 1.0000 | 0.9821 | 0.9167 |
| Hybrid + Rerank | 1.0000 | 0.9821 | 0.9167 |
| Hybrid + Rerank (Chunk=256) | 0.8000 | 0.7500 | 0.7917 |

## Latency Breakdown by Stage

The concurrent retrievers run in parallel, so retrieval latency is dominated by the slower retriever.

| Configuration | Pipeline Stage | Subcomponent / Action | Avg Time (ms) | % of Profiled Time |
| :--- | :--- | :--- | :---: | :---: |
| Hybrid + Rerank | Query Embedding | LiteLLM call (Gemini API network call) | 0.32 ms | 1.3% |
| Hybrid + Rerank | Dense Retrieval | ChromaDB query for top-50 vector matches | 22.02 ms | 87.1% |
| Hybrid + Rerank | Sparse Retrieval | PostgreSQL GIN index / ts_rank query for top-50 matches | 2.81 ms | 11.1% |
| Hybrid + Rerank | Rrf Fusion | Reciprocal Rank Fusion blending of result sets | 0.05 ms | 0.2% |
| Hybrid + Rerank | Reranking | Cross-Encoder inference over top candidate pairs | 0.10 ms | 0.4% |
| Hybrid + Rerank (Chunk=256) | Query Embedding | LiteLLM call (Gemini API network call) | 0.36 ms | 1.3% |
| Hybrid + Rerank (Chunk=256) | Dense Retrieval | ChromaDB query for top-50 vector matches | 23.67 ms | 88.6% |
| Hybrid + Rerank (Chunk=256) | Sparse Retrieval | PostgreSQL GIN index / ts_rank query for top-50 matches | 2.55 ms | 9.5% |
| Hybrid + Rerank (Chunk=256) | Rrf Fusion | Reciprocal Rank Fusion blending of result sets | 0.07 ms | 0.3% |
| Hybrid + Rerank (Chunk=256) | Reranking | Cross-Encoder inference over top candidate pairs | 0.06 ms | 0.2% |

## Findings & Observations

1. **The cross-encoder re-ranker increases MRR by `+0.0000`.** The saved results show `Hybrid RRF` at `0.9667` and `Hybrid + Rerank` at `0.9667`. A general MS MARCO-style re-ranker can be domain-mismatched for legal clause retrieval and should be validated before being presented as an automatic improvement.
2. **Dense retrieval dominates the aggregate set.** Dense Only reaches `0.9556` MRR while Sparse Only reaches `0.3778`. That confirms the current legal queries are better served by embedding semantics than keyword overlap alone.
3. **Hybrid RRF changes MRR by `+0.0111` versus Dense Only.** Use the per-category breakdown to determine whether sparse retrieval helps keyword-style queries enough to justify its overhead.
4. **Precision@5 is capped by the ground truth design.** Each query currently has one relevant chunk, so the best possible Precision@5 is `1 / 5 = 0.2000`. The low P@5 values should be described as a labeling limitation, not as evidence that the top result is usually wrong.
5. **The 350ms latency target is not met in the saved local run.** Dense Only averages `1224.99 ms`, and the other neural configurations are in the same range. Treat this as a local inference or embedding-call bottleneck until the stage-level profile proves otherwise.
6. **Reducing chunk size significantly decreases retrieval accuracy.** Reducing chunk size from 1024 tokens (`Hybrid + Rerank` at `0.9667` MRR) to 256 tokens (`Hybrid + Rerank (Chunk=256)` at `0.7667` MRR) reduces MRR by `-0.2000`. Smaller chunk sizes restrict the semantic context of legal clauses, causing retrieval gaps.

## Next Steps

1. Evaluate `BAAI/bge-reranker-base` as an alternative cross-encoder; it is trained on a broader retrieval corpus and may generalize better to legal text without domain fine-tuning.