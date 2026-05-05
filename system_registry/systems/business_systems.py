from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression

from system_registry.base import AISystem, SystemOutput


def _features(row: dict[str, Any]) -> np.ndarray:
    return np.array(
        [
            float(row.get("f0", 0.0)),
            float(row.get("f1", 0.0)),
            float(row.get("f2", 0.0)),
        ],
        dtype=np.float32,
    ).reshape(1, -1)


class RankingModel(AISystem):
    system_id = "RankingModel"
    description = "Lightweight linear scoring model for listwise reranking (local sklearn)."

    def run(self, input: dict) -> SystemOutput:
        self.validate_input(input, ("candidates",))
        candidates: list[dict[str, Any]] = list(input["candidates"])
        w = np.array([float(x) for x in input.get("weights", [0.4, 0.35, 0.25])], dtype=np.float32)
        scores: dict[str, float] = {}
        for c in candidates:
            x = _features(c).reshape(-1)
            s = float(np.dot(w[: x.shape[0]], x[: w.shape[0]]))
            cid = str(c.get("id"))
            scores[cid] = s
        ranked = sorted(scores.keys(), key=lambda i: scores[i], reverse=True)
        hits = [{"id": i, "score": scores[i]} for i in ranked]
        return SystemOutput(self.system_id, payload={"ranked": hits}, ranked_ids=ranked, scores=scores)


class RecommendationModel(AISystem):
    system_id = "RecommendationModel"
    description = "Nearest-neighbor style recommendations in feature space (cosine)."

    def run(self, input: dict) -> SystemOutput:
        self.validate_input(input, ("user_vector", "catalog"))
        uv = np.array(list(input["user_vector"]), dtype=np.float32).reshape(1, -1)
        catalog: list[dict[str, Any]] = list(input["catalog"])
        k = int(input.get("top_k", 5))
        best: list[tuple[float, str]] = []
        for item in catalog:
            iv = np.array(list(item.get("vector", [0, 0, 0])), dtype=np.float32).reshape(1, -1)
            denom = (np.linalg.norm(uv) * np.linalg.norm(iv) + 1e-9)
            sim = float((uv @ iv.T).reshape(-1)[0] / denom)
            best.append((sim, str(item.get("id"))))
        best.sort(reverse=True)
        top = best[:k]
        scores = {i: s for s, i in top}
        ranked = [i for _, i in top]
        return SystemOutput(self.system_id, payload={"recommendations": top}, ranked_ids=ranked, scores=scores)


class PredictionModel(AISystem):
    system_id = "PredictionModel"
    description = "Train-on-the-fly logistic regression for tabular rows (local, tiny)."

    def run(self, input: dict) -> SystemOutput:
        self.validate_input(input, ("rows",))
        rows: list[dict[str, Any]] = list(input["rows"])
        if not rows:
            return SystemOutput(self.system_id, payload={"probs": []}, ranked_ids=[], scores={})

        has_label = "label" in rows[0]
        X = np.vstack([_features(r) for r in rows])
        if has_label and len(rows) >= 2:
            y = np.array([int(r["label"]) for r in rows], dtype=np.int32)
            clf = LogisticRegression(max_iter=200)
            clf.fit(X, y)
            probs = clf.predict_proba(X)[:, 1].tolist()
        else:
            probs = [float(1 / (1 + np.exp(-(X[i].sum())))) for i in range(X.shape[0])]

        out_rows = []
        scores: dict[str, float] = {}
        for i, r in enumerate(rows):
            rid = str(r.get("id", str(i)))
            scores[rid] = float(probs[i])
            out_rows.append({"id": rid, "p_positive": float(probs[i])})
        ranked = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        return SystemOutput(
            self.system_id,
            payload={"rows": out_rows, "trained": has_label and len(rows) >= 2},
            ranked_ids=ranked,
            scores=scores,
        )
