import sys
import os
import pytest

# Add the workspace root to sys.path so we can import eval modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from eval.metrics import precision_at_k, mean_reciprocal_rank, ndcg_at_k

def test_precision_at_k():
    relevant = {"c1", "c3"}
    
    # Perfect retrieval in top 2
    assert precision_at_k(["c1", "c3", "c5"], relevant, 2) == 1.0
    
    # 1 out of 2 relevant in top 2
    assert precision_at_k(["c1", "c2", "c3"], relevant, 2) == 0.5
    
    # 0 out of 2 relevant in top 2
    assert precision_at_k(["c2", "c4", "c1"], relevant, 2) == 0.0
    
    # k larger than retrieved list
    assert precision_at_k(["c1"], relevant, 5) == 0.2
    
    # Edge cases
    assert precision_at_k([], relevant, 3) == 0.0
    assert precision_at_k(["c1"], set(), 3) == 0.0
    assert precision_at_k(["c1"], relevant, 0) == 0.0
    assert precision_at_k(["c1"], relevant, -1) == 0.0

def test_mean_reciprocal_rank():
    # Query 1: relevant {"c2"}, retrieved ["c1", "c2", "c3"] -> rank 2, rr = 0.5
    # Query 2: relevant {"c1"}, retrieved ["c1", "c2"] -> rank 1, rr = 1.0
    # Query 3: relevant {"c4"}, retrieved ["c1", "c2", "c3"] -> no match, rr = 0.0
    # MRR = (0.5 + 1.0 + 0.0) / 3 = 0.5
    
    retrieved_lists = [
        ["c1", "c2", "c3"],
        ["c1", "c2"],
        ["c1", "c2", "c3"]
    ]
    relevant_sets = [
        {"c2"},
        {"c1"},
        {"c4"}
    ]
    
    assert mean_reciprocal_rank(retrieved_lists, relevant_sets) == 0.5
    
    # Edge cases
    assert mean_reciprocal_rank([], []) == 0.0
    assert mean_reciprocal_rank([["c1"]], [set()]) == 0.0

def test_ndcg_at_k():
    relevant = {"c1", "c2"}
    
    # DCG@2: 1/log2(2) + 1/log2(3) = 1.0 + 0.63092975 = 1.63092975
    # IDCG@2: same (perfect retrieval of 2 relevant items)
    # NDCG@2 should be 1.0
    assert abs(ndcg_at_k(["c1", "c2"], relevant, 2) - 1.0) < 1e-6
    
    # DCG@3: retrieved ["c3", "c1", "c2"]
    # c3 is not relevant. c1 at rank 2 (idx 1), c2 at rank 3 (idx 2)
    # DCG@3 = 0 + 1/log2(3) + 1/log2(4) = 0.63092975 + 0.5 = 1.13092975
    # IDCG@3 = DCG of perfect list ["c1", "c2", "c3"] = 1.0 + 0.63092975 = 1.63092975
    # NDCG@3 = 1.13092975 / 1.63092975 = 0.693426
    expected_ndcg = 1.1309297535714575 / 1.6309297535714575
    assert abs(ndcg_at_k(["c3", "c1", "c2"], relevant, 3) - expected_ndcg) < 1e-6
    
    # Edge cases
    assert ndcg_at_k([], relevant, 3) == 0.0
    assert ndcg_at_k(["c1"], set(), 3) == 0.0
    assert ndcg_at_k(["c1"], relevant, 0) == 0.0
    assert ndcg_at_k(["c1"], relevant, -2) == 0.0
