from __future__ import annotations

import math


def recall_at_k(ranked_ids: list[str] | None, relevant_ids: set[str], k: int) -> float:
    if not ranked_ids or not relevant_ids:
        return 0.0
    top = ranked_ids[:k]
    hits = sum(1 for d in top if d in relevant_ids)
    return hits / float(len(relevant_ids))


def mean_reciprocal_rank(ranked_ids: list[str] | None, relevant_ids: set[str]) -> float:
    if not ranked_ids or not relevant_ids:
        return 0.0
    for i, doc_id in enumerate(ranked_ids, start=1):
        if doc_id in relevant_ids:
            return 1.0 / float(i)
    return 0.0


def ndcg_at_k(ranked_ids: list[str] | None, relevant_ids: set[str], k: int) -> float:
    if not ranked_ids or not relevant_ids:
        return 0.0
    top = ranked_ids[:k]
    gains = [1.0 if doc_id in relevant_ids else 0.0 for doc_id in top]
    dcg = gains[0]
    for i in range(1, len(gains)):
        dcg += gains[i] / math.log2(i + 1)
    ideal_len = min(k, len(relevant_ids))
    ideal_gains = [1.0] * ideal_len + [0.0] * (k - ideal_len)
    idcg = ideal_gains[0]
    for i in range(1, len(ideal_gains)):
        idcg += ideal_gains[i] / math.log2(i + 1)
    if idcg <= 0:
        return 0.0
    return float(dcg / idcg)


def accuracy_score(prediction: str | None, reference: str | None) -> float:
    if prediction is None or reference is None:
        return 0.0
    p = prediction.strip().lower()
    r = reference.strip().lower()
    if not p or not r:
        return 0.0
    return 1.0 if p == r else (1.0 if r in p or p in r else 0.0)


def numeric_labels_match(pred: float | int | None, label: float | int | None, tol: float = 1e-6) -> float:
    if pred is None or label is None:
        return 0.0
    return 1.0 if abs(float(pred) - float(label)) <= tol else 0.0
