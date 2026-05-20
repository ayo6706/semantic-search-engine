import json
import os


QUERY_TYPE_LABELS = {
    "keyword": "Keyword Queries",
    "semantic": "Semantic Queries",
    "hybrid": "Hybrid Queries",
}


def has_category_breakdown(results: dict) -> bool:
    return any(metrics.get("category_breakdown") for metrics in results.values())


def has_stage_latencies(results: dict) -> bool:
    return any(metrics.get("stage_latencies_ms") for metrics in results.values())


def metric_delta(results: dict, left: str, right: str, metric: str) -> float | None:
    if left not in results or right not in results:
        return None

    return results[left][metric] - results[right][metric]


def same_metrics(results: dict, left: str, right: str) -> bool:
    if left not in results or right not in results:
        return False

    keys = ("mrr", "ndcg10", "p5")
    return all(abs(results[left][key] - results[right][key]) < 0.0001 for key in keys)


def generate_markdown_report(results: dict) -> str:
    lines = [
        "# Retrieval Ablation Evaluation Report",
        "",
        "This report summarizes the retrieval accuracy and latency across different configurations of the search pipeline. The evaluation dataset consists of 45 queries (15 keyword, 15 semantic, and 15 hybrid) evaluated against 3 test legal documents.",
        "",
        "## Overall Ablation Comparison",
        "",
        "| Configuration | MRR | NDCG@10 | Precision@5 | Latency (ms) |",
        "| :--- | :---: | :---: | :---: | :---: |"
    ]
    
    for config, metrics in results.items():
        lines.append(
            f"| {config} | {metrics['mrr']:.4f} | {metrics['ndcg10']:.4f} | "
            f"{metrics['p5']:.4f} | {metrics['latency_ms']:.2f} ms |"
        )
        
    lines.append("")

    if has_category_breakdown(results):
        lines.append("## Retrieval Accuracy by Query Type (MRR)")
        lines.append("")
        lines.append("| Configuration | Keyword Queries | Semantic Queries | Hybrid Queries |")
        lines.append("| :--- | :---: | :---: | :---: |")

        for config, metrics in results.items():
            breakdown = metrics.get("category_breakdown", {})
            values = []
            for query_type in QUERY_TYPE_LABELS:
                query_metrics = breakdown.get(query_type)
                values.append(f"{query_metrics['mrr']:.4f}" if query_metrics else "N/A")
            lines.append(f"| {config} | {' | '.join(values)} |")

        lines.append("")
    else:
        lines.append("## Retrieval Accuracy by Query Type")
        lines.append("")
        lines.append("The current saved results do not include per-category metrics. Re-run `python eval/runner.py` to populate the keyword, semantic, and hybrid MRR breakdowns added to the evaluator.")
        lines.append("")

    if has_stage_latencies(results):
        lines.append("## Latency Breakdown by Stage")
        lines.append("")
        lines.append("The concurrent retrievers run in parallel, so retrieval latency is dominated by the slower retriever.")
        lines.append("")
        lines.append("| Configuration | Pipeline Stage | Subcomponent / Action | Avg Time (ms) | % of Profiled Time |")
        lines.append("| :--- | :--- | :--- | :---: | :---: |")

        for config, metrics in results.items():
            stage_latencies = metrics.get("stage_latencies_ms")
            if not stage_latencies:
                continue

            total_lat = sum(stage_latencies.values())
            for stage, time_ms in stage_latencies.items():
                pct = (time_ms / total_lat) * 100 if total_lat > 0 else 0.0
                stage_name = stage.replace("_", " ").title()
                lines.append(f"| {config} | {stage_name} | {get_stage_detail(stage)} | {time_ms:.2f} ms | {pct:.1f}% |")

        lines.append("")
    else:
        lines.append("## Latency Breakdown by Stage")
        lines.append("")
        lines.append("The current saved results only include end-to-end latency. Re-run `python eval/runner.py` to populate stage-level timings for query embedding, dense retrieval, sparse retrieval, RRF fusion, and reranking.")
        lines.append("")

    lines.append("## Findings & Observations")
    lines.append("")
    findings = []

    rerank_delta = metric_delta(results, "Hybrid + Rerank", "Hybrid RRF", "mrr")
    if rerank_delta is not None:
        direction = "decreases" if rerank_delta < 0 else "increases"
        findings.append(
            f"**The cross-encoder re-ranker {direction} MRR by `{rerank_delta:+.4f}`.** "
            f"The saved results show `Hybrid RRF` at `{results['Hybrid RRF']['mrr']:.4f}` "
            f"and `Hybrid + Rerank` at `{results['Hybrid + Rerank']['mrr']:.4f}`. "
            "A general MS MARCO-style re-ranker can be domain-mismatched for legal clause retrieval "
            "and should be validated before being presented as an automatic improvement."
        )

    dense_mrr = results.get("Dense Only", {}).get("mrr")
    sparse_mrr = results.get("Sparse Only", {}).get("mrr")
    if dense_mrr is not None and sparse_mrr is not None:
        findings.append(
            f"**Dense retrieval dominates the aggregate set.** Dense Only reaches `{dense_mrr:.4f}` "
            f"MRR while Sparse Only reaches `{sparse_mrr:.4f}`. That confirms the current legal "
            "queries are better served by embedding semantics than keyword overlap alone."
        )

    hybrid_delta = metric_delta(results, "Hybrid RRF", "Dense Only", "mrr")
    if hybrid_delta is not None:
        if abs(hybrid_delta) < 0.0001:
            findings.append(
                "**Hybrid RRF matches dense retrieval but does not improve it on this saved run.** "
                "The identical MRR and NDCG@10 indicate BM25 is not changing the top-ranked "
                "relevant result for the aggregate metrics. It remains a useful safety net for "
                "exact-match queries, but the current aggregate does not prove a gain."
            )
        else:
            findings.append(
                f"**Hybrid RRF changes MRR by `{hybrid_delta:+.4f}` versus Dense Only.** "
                "Use the per-category breakdown to determine whether sparse retrieval helps "
                "keyword-style queries enough to justify its overhead."
            )

    max_p5 = max(metrics["p5"] for metrics in results.values())
    if max_p5 <= 0.2001:
        findings.append(
            "**Precision@5 is capped by the ground truth design.** Each query currently has one "
            "relevant chunk, so the best possible Precision@5 is `1 / 5 = 0.2000`. The low P@5 "
            "values should be described as a labeling limitation, not as evidence that the top "
            "result is usually wrong."
        )

    dense_latency = results.get("Dense Only", {}).get("latency_ms")
    if dense_latency is not None:
        findings.append(
            f"**The 350ms latency target is not met in the saved local run.** Dense Only averages "
            f"`{dense_latency:.2f} ms`, and the other neural configurations are in the same range. "
            "Treat this as a local inference or embedding-call bottleneck until the stage-level "
            "profile proves otherwise."
        )

    if same_metrics(results, "Hybrid + Rerank", "Hybrid + Rerank (Chunk=512)"):
        findings.append(
            "**The saved Chunk=512 row is not a meaningful ablation.** It is identical to "
            "`Hybrid + Rerank` on MRR, NDCG@10, and Precision@5. A portfolio report should "
            "compare distinct 256, 512, and 1024 chunk-size runs generated from the same evaluator version."
        )
    elif "Hybrid + Rerank (Chunk=256)" in results and "Hybrid + Rerank (Chunk=512)" in results:
        findings.append(
            "**Chunk-size comparisons are now present.** Interpret them as an ablation only when "
            "all rows were produced by the same evaluator run and ingestion settings."
        )

    for index, finding in enumerate(findings, start=1):
        lines.append(f"{index}. {finding}")

    lines.append("")
    lines.append("## Next Steps")
    lines.append("")
    next_steps = []
    if not has_category_breakdown(results) or not has_stage_latencies(results) or "Hybrid + Rerank (Chunk=256)" not in results:
        next_steps.append("Re-run `python eval/runner.py` so `evaluation_results.json` includes the category breakdown, stage latencies, and distinct 256, 512, and 1024 chunk-size runs.")
    if not has_category_breakdown(results):
        next_steps.append("Add the per-category MRR table to the portfolio narrative once populated; that is where sparse retrieval should prove its value on exact keyword queries.")
    if not has_stage_latencies(results):
        next_steps.append("Use the stage-latency table to identify whether query embedding, vector retrieval, database full-text search, fusion, or reranking is the real bottleneck.")
    next_steps.append("Evaluate `BAAI/bge-reranker-base` as an alternative cross-encoder; it is trained on a broader retrieval corpus and may generalize better to legal text without domain fine-tuning.")
    if not next_steps:
        next_steps.append("Use the category and stage-latency tables above to decide whether hybrid retrieval and reranking justify their added complexity.")

    for index, step in enumerate(next_steps, start=1):
        lines.append(f"{index}. {step}")
    
    report_content = "\n".join(lines)
    
    report_dir = os.path.dirname(__file__)
    report_path = os.path.join(report_dir, "report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)
        
    print("\n" + "=" * 50)
    print("RETRIEVAL EVALUATION REPORT GENERATED:")
    print("=" * 50)
    print(report_content)
    print("=" * 50)
    print(f"Report saved to: {report_path}")
    
    return report_content

def get_stage_detail(stage: str) -> str:
    details = {
        "query_embedding": "LiteLLM call (Gemini API network call)",
        "dense_retrieval": "ChromaDB query for top-50 vector matches",
        "sparse_retrieval": "PostgreSQL GIN index / ts_rank query for top-50 matches",
        "rrf_fusion": "Reciprocal Rank Fusion blending of result sets",
        "reranking": "Cross-Encoder inference over top candidate pairs"
    }
    return details.get(stage, "")

if __name__ == "__main__":
    results_path = os.path.join(os.path.dirname(__file__), "datasets/evaluation_results.json")
    if os.path.exists(results_path):
        with open(results_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        generate_markdown_report(data)
    else:
        print(f"No evaluation results found at {results_path}. Please run eval/runner.py first.")
