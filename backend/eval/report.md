# Retrieval Ablation Evaluation Report

This report summarizes the retrieval accuracy and latency across different configurations of the search pipeline. The evaluation dataset consists of 45 queries (15 keyword, 15 semantic, and 15 hybrid) evaluated against 3 test legal documents.

## Overall Ablation Comparison

| Configuration | MRR | NDCG@10 | Precision@5 | Latency (ms) |
| :--- | :---: | :---: | :---: | :---: |
| Dense Only | 0.9370 | 0.9532 | 0.2000 | 10.00 ms |
| Sparse Only | 0.3778 | 0.3778 | 0.0756 | 1.06 ms |
| Hybrid RRF | 0.9370 | 0.9532 | 0.2000 | 11.51 ms |
| Hybrid + Rerank (Chunk=1024) | 0.9333 | 0.9503 | 0.2000 | 17.97 ms |
| Hybrid + Rerank (Chunk=256) | 0.7796 | 0.8072 | 0.1778 | 11.65 ms |

## Measurement Protocol

Latency is reported as mean per-query wall-clock time across 135 measured queries (45 queries x 3 measured run(s)) after 1 warm-up run(s).
Sub-millisecond query embedding times indicate a cached or local embedding path, not a live network call to Gemini. Compare latency rows only when they were produced by the same warm-up and cache policy.

## Retrieval Accuracy by Query Type (MRR)

| Configuration | Keyword Queries | Semantic Queries | Hybrid Queries |
| :--- | :---: | :---: | :---: |
| Dense Only | 1.0000 | 0.9167 | 0.9583 |
| Sparse Only | 0.6000 | 0.3214 | 0.4167 |
| Hybrid RRF | 1.0000 | 0.9167 | 0.9583 |
| Hybrid + Rerank (Chunk=1024) | 1.0000 | 0.9107 | 0.9583 |
| Hybrid + Rerank (Chunk=256) | 0.9000 | 0.7589 | 0.7778 |

## Latency Breakdown by Stage

The concurrent retrievers run in parallel, so retrieval latency is dominated by the slower retriever. `Avg Time` is the mean per measured query for the profiled configuration, using the measurement protocol above.

| Configuration | Pipeline Stage | Subcomponent / Action | Avg Time (ms) | % of Profiled Time |
| :--- | :--- | :--- | :---: | :---: |
| Hybrid + Rerank (Chunk=1024) | Query Embedding | Embedding lookup/call through LiteLLM provider | 0.01 ms | 0.1% |
| Hybrid + Rerank (Chunk=1024) | Dense Retrieval | ChromaDB query for top-50 vector matches | 17.87 ms | 88.5% |
| Hybrid + Rerank (Chunk=1024) | Sparse Retrieval | PostgreSQL GIN index / ts_rank query for top-50 matches | 2.21 ms | 10.9% |
| Hybrid + Rerank (Chunk=1024) | Rrf Fusion | Reciprocal Rank Fusion blending of result sets | 0.05 ms | 0.2% |
| Hybrid + Rerank (Chunk=1024) | Reranking | Cross-Encoder inference over top candidate pairs | 0.05 ms | 0.2% |
| Hybrid + Rerank (Chunk=256) | Query Embedding | Embedding lookup/call through LiteLLM provider | 0.01 ms | 0.1% |
| Hybrid + Rerank (Chunk=256) | Dense Retrieval | ChromaDB query for top-50 vector matches | 11.56 ms | 87.9% |
| Hybrid + Rerank (Chunk=256) | Sparse Retrieval | PostgreSQL GIN index / ts_rank query for top-50 matches | 1.50 ms | 11.4% |
| Hybrid + Rerank (Chunk=256) | Rrf Fusion | Reciprocal Rank Fusion blending of result sets | 0.04 ms | 0.3% |
| Hybrid + Rerank (Chunk=256) | Reranking | Cross-Encoder inference over top candidate pairs | 0.04 ms | 0.3% |

## Findings & Observations

1. **Recommended configuration:** Use Hybrid RRF with 1024-token chunks for this benchmark. It matches Dense Only accuracy at `0.9370` MRR, keeps warm-cache latency low at `11.51 ms`, preserves sparse exact-match coverage as the corpus grows, and avoids the reranker's semantic-query regression.
2. **The cross-encoder re-ranker decreases MRR by `-0.0037`.** The saved results show `Hybrid RRF` at `0.9370` and `Hybrid + Rerank (Chunk=1024)` at `0.9333`. A general MS MARCO-style re-ranker can be domain-mismatched for legal clause retrieval and should be validated before being presented as an automatic improvement.
3. **Dense retrieval dominates the aggregate set.** Dense Only reaches `0.9370` MRR while Sparse Only reaches `0.3778`. That confirms the current legal queries are better served by embedding semantics than keyword overlap alone.
4. **Hybrid RRF matches dense retrieval but does not improve it on this saved run.** The identical MRR and NDCG@10 indicate BM25 is not changing the top-ranked relevant result for the aggregate metrics. It remains a useful safety net for exact-match queries, but the current aggregate does not prove a gain.
5. **Precision@5 is capped by the ground truth design.** Each query currently has one relevant chunk, so the best possible Precision@5 is `1 / 5 = 0.2000`. The low P@5 values should be described as a labeling limitation, not as evidence that the top result is usually wrong.
6. **The warmed local run meets the 350ms latency target.** Dense Only averages `10.00 ms` after the configured warm-up. This should be presented as warm-cache retrieval latency, because the stage profile shows cached/local query embeddings rather than live Gemini network calls.
7. **Reducing chunk size significantly decreases retrieval accuracy.** Reducing chunk size from 1024 tokens (`Hybrid + Rerank (Chunk=1024)` at `0.9333` MRR) to 256 tokens (`Hybrid + Rerank (Chunk=256)` at `0.7796` MRR) reduces MRR by `-0.1537`. Smaller chunk sizes restrict the semantic context of legal clauses, causing retrieval gaps.

## Next Steps

1. Evaluate `BAAI/bge-reranker-base` as an alternative cross-encoder; it is trained on a broader retrieval corpus and may generalize better to legal text without domain fine-tuning.
2. Expand the ground truth to 2-3 relevant chunks per query with graded labels such as exact relevance and partial relevance; this would make Precision@5 and NDCG@10 more discriminating.