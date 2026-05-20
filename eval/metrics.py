import math

def precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Calculate Precision at k (P@k).
    
    P@k = |retrieved[:k] intersect relevant| / k
    """
    if k <= 0:
        return 0.0
    
    # Take at most k retrieved items
    retrieved_k = retrieved[:k]
    if not retrieved_k:
        return 0.0
        
    overlap = len(set(retrieved_k) & relevant)
    return overlap / k

def mean_reciprocal_rank(retrieved_lists: list[list[str]], relevant_sets: list[set[str]]) -> float:
    """Calculate Mean Reciprocal Rank (MRR) across a list of queries.
    
    MRR = (1 / N) * sum(1 / rank_i)
    where rank_i is the 1-indexed rank of the first relevant document retrieved.
    If no relevant documents are retrieved, reciprocal rank is 0.
    """
    if not retrieved_lists or not relevant_sets:
        return 0.0
        
    total_rr = 0.0
    for retrieved, relevant in zip(retrieved_lists, relevant_sets):
        # Find first matching rank
        rr = 0.0
        for idx, item in enumerate(retrieved):
            if item in relevant:
                rr = 1.0 / (idx + 1)
                break
        total_rr += rr
        
    return total_rr / len(retrieved_lists)

def ndcg_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Calculate Normalized Discounted Cumulative Gain at k (NDCG@k).
    
    NDCG@k = DCG@k / IDCG@k
    Using binary relevance (rel_i in {0, 1}).
    """
    if k <= 0 or not relevant:
        return 0.0
        
    # Calculate DCG@k
    dcg = 0.0
    retrieved_k = retrieved[:k]
    for idx, item in enumerate(retrieved_k):
        if item in relevant:
            dcg += 1.0 / math.log2(idx + 2)
            
    # Calculate IDCG@k (Ideal DCG@k)
    # The ideal case puts min(k, |relevant|) relevant items at the top
    ideal_relevant_count = min(k, len(relevant))
    if ideal_relevant_count == 0:
        return 0.0
        
    idcg = sum(1.0 / math.log2(j + 2) for j in range(ideal_relevant_count))
    
    if idcg == 0.0:
        return 0.0
        
    return dcg / idcg
