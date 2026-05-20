# Retrieval Ablation Evaluation Report

This report summarizes the retrieval accuracy and latency across different configurations of the search pipeline. The evaluation dataset consists of 45 queries (15 keyword, 15 semantic, and 15 hybrid) evaluated against 3 test legal documents.

## Overall Ablation Comparison

| Configuration | MRR | NDCG@10 | Precision@5 | Latency (ms) |
| :--- | :---: | :---: | :---: | :---: |
| Dense Only | 0.9370 | 0.9532 | 0.2000 | 829.03 ms |
| Sparse Only | 0.3778 | 0.3778 | 0.0756 | 4.59 ms |
| Hybrid RRF | 0.9370 | 0.9532 | 0.2000 | 763.97 ms |
| Hybrid + Rerank | 0.9333 | 0.9503 | 0.2000 | 838.53 ms |
| Hybrid + Rerank (Chunk=512) | 0.9333 | 0.9503 | 0.2000 | 828.92 ms |

## Retrieval Accuracy by Query Type

The current saved results do not include per-category metrics. Re-run `python eval/runner.py` to populate the keyword, semantic, and hybrid MRR breakdowns added to the evaluator.

## Latency Breakdown by Stage

The current saved results only include end-to-end latency. Re-run `python eval/runner.py` to populate stage-level timings for query embedding, dense retrieval, sparse retrieval, RRF fusion, and reranking.

## Findings & Observations

1. **The cross-encoder re-ranker decreases MRR by `-0.0037`.** The saved results show `Hybrid RRF` at `0.9370` and `Hybrid + Rerank` at `0.9333`. A general MS MARCO-style re-ranker can be domain-mismatched for legal clause retrieval and should be validated before being presented as an automatic improvement.
2. **Dense retrieval dominates the aggregate set.** Dense Only reaches `0.9370` MRR while Sparse Only reaches `0.3778`. That confirms the current legal queries are better served by embedding semantics than keyword overlap alone.
3. **Hybrid RRF matches dense retrieval but does not improve it on this saved run.** The identical MRR and NDCG@10 indicate BM25 is not changing the top-ranked relevant result for the aggregate metrics. It remains a useful safety net for exact-match queries, but the current aggregate does not prove a gain.
4. **Precision@5 is capped by the ground truth design.** Each query currently has one relevant chunk, so the best possible Precision@5 is `1 / 5 = 0.2000`. The low P@5 values should be described as a labeling limitation, not as evidence that the top result is usually wrong.
5. **The 350ms latency target is not met in the saved local run.** Dense Only averages `829.03 ms`, and the other neural configurations are in the same range. Treat this as a local inference or embedding-call bottleneck until the stage-level profile proves otherwise.
6. **The saved Chunk=512 row is not a meaningful ablation.** It is identical to `Hybrid + Rerank` on MRR, NDCG@10, and Precision@5. A portfolio report should compare distinct 256, 512, and 1024 chunk-size runs generated from the same evaluator version.

## Next Steps

1. Re-run `python eval/runner.py` so `evaluation_results.json` includes the category breakdown, stage latencies, and distinct 256, 512, and 1024 chunk-size runs.
2. Add the per-category MRR table to the portfolio narrative once populated; that is where sparse retrieval should prove its value on exact keyword queries.
3. Use the stage-latency table to identify whether query embedding, vector retrieval, database full-text search, fusion, or reranking is the real bottleneck.
4. Evaluate `BAAI/bge-reranker-base` as an alternative cross-encoder; it is trained on a broader retrieval corpus and may generalize better to legal text without domain fine-tuning.