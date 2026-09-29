"""
Embedding-based event clustering and deduplication.

Replaces title-similarity dedup with semantic grouping: articles about the
same event cluster together even when outlets phrase headlines differently
("Iran threatens oil exports" / "Tehran warns it may halt Gulf crude").
Clusters become event groups that downstream selection uses to (a) prefer
well-corroborated, perspective-diverse events and (b) tell the analyzer
which articles describe the same event.

Stack: fastembed (ONNX MiniLM, CPU, no torch) + scikit-learn HDBSCAN.
Everything is soft-dependency guarded — when models can't load (offline CI,
missing package) callers fall back to the legacy title-similarity dedup.
"""

import logging
from typing import List, Optional, Tuple

import numpy as np

from ..models import Article

logger = logging.getLogger(__name__)

EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
NEAR_DUPLICATE_COSINE = 0.97   # same text syndicated/reposted
MIN_CLUSTER_SIZE = 2
# HDBSCAN with min_cluster_size=2 splits one big event into several small
# clusters and leaves outlying reports as noise; on 2026-09-29 the US-Iran
# talks story showed no Western outlet in its grid although Western outlets
# ran it. Conservative repair passes (high thresholds: a false merge would
# fuse two events, which is worse than a split):
MERGE_CENTROID_COSINE = 0.85   # two clusters whose centroids are this close are one event
ATTACH_NOISE_COSINE = 0.75     # a noise article this close to a centroid joins that event


class EmbeddingClusterer:
    """Semantic event clustering over article embeddings."""

    def __init__(self):
        self._model = None
        self._available: Optional[bool] = None

    def available(self) -> bool:
        """Lazily verify that the embedding stack can actually run."""
        if self._available is None:
            try:
                from fastembed import TextEmbedding
                from sklearn.cluster import HDBSCAN  # noqa: F401 (availability check)
                self._model = TextEmbedding(model_name=EMBED_MODEL)
                self._available = True
                logger.info(f"Embedding clusterer ready ({EMBED_MODEL})")
            except Exception as e:
                logger.warning(f"Embedding clusterer unavailable, falling back to title dedup: {e}")
                self._available = False
        return self._available

    def _embed(self, articles: List[Article]) -> np.ndarray:
        texts = [
            f"{a.title}. {(a.summary or '')[:300]}"
            for a in articles
        ]
        vectors = np.array(list(self._model.embed(texts)), dtype=np.float32)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vectors / norms

    def dedupe_and_tag(self, articles: List[Article]) -> Tuple[List[Article], int]:
        """Remove near-duplicates and tag each article with its event cluster.

        Returns (articles, event_count). Articles in the same semantic cluster
        get the same `cluster_id` ("event_N"); noise points stay untagged.
        Near-identical pairs (cosine > 0.97) are collapsed, keeping the
        higher-weight source.
        """
        if len(articles) < 3 or not self.available():
            return articles, 0

        from sklearn.cluster import HDBSCAN

        vectors = self._embed(articles)

        # HDBSCAN with euclidean on unit vectors is monotonic in cosine distance.
        labels = HDBSCAN(min_cluster_size=MIN_CLUSTER_SIZE, metric="euclidean").fit_predict(vectors)
        labels = self._repair_fragments(vectors, np.array(labels))

        # Near-duplicate removal inside clusters
        drop = set()
        by_label = {}
        for i, label in enumerate(labels):
            if label >= 0:
                by_label.setdefault(label, []).append(i)
        for members in by_label.values():
            for pos_a in range(len(members)):
                i = members[pos_a]
                if i in drop:
                    continue
                for pos_b in range(pos_a + 1, len(members)):
                    j = members[pos_b]
                    if j in drop:
                        continue
                    if float(np.dot(vectors[i], vectors[j])) >= NEAR_DUPLICATE_COSINE:
                        a, b = articles[i], articles[j]
                        loser = j if (a.source_weight or 1.0) >= (b.source_weight or 1.0) else i
                        drop.add(loser)
                        if loser == i:
                            break

        kept: List[Article] = []
        event_ids = {}
        for i, article in enumerate(articles):
            if i in drop:
                continue
            label = int(labels[i])
            if label >= 0:
                if label not in event_ids:
                    event_ids[label] = f"event_{len(event_ids) + 1}"
                article.cluster_id = event_ids[label]
            else:
                article.cluster_id = None
            kept.append(article)

        logger.info(
            f"Embedding clustering: {len(articles)} articles -> {len(kept)} kept "
            f"({len(drop)} near-duplicates removed), {len(event_ids)} events"
        )
        return kept, len(event_ids)

    @staticmethod
    def _centroids(vectors: np.ndarray, labels: np.ndarray) -> dict:
        cents = {}
        for label in sorted(set(int(l) for l in labels if l >= 0)):
            c = vectors[labels == label].mean(axis=0)
            n = np.linalg.norm(c)
            cents[label] = c / n if n else c
        return cents

    @classmethod
    def _repair_fragments(cls, vectors: np.ndarray, labels: np.ndarray) -> np.ndarray:
        """Merge near-identical clusters, then attach close noise points.

        Both passes use centroid cosine similarity with conservative
        thresholds, so only fragments of the same event are rejoined."""
        labels = labels.copy()
        merged = attached = 0

        # 1) merge clusters (union-find over centroid pairs)
        cents = cls._centroids(vectors, labels)
        keys = list(cents)
        parent = {k: k for k in keys}

        def find(k):
            while parent[k] != k:
                parent[k] = parent[parent[k]]
                k = parent[k]
            return k

        for i, a in enumerate(keys):
            for b in keys[i + 1:]:
                if float(np.dot(cents[a], cents[b])) >= MERGE_CENTROID_COSINE:
                    ra, rb = find(a), find(b)
                    if ra != rb:
                        parent[rb] = ra
                        merged += 1
        for idx, label in enumerate(labels):
            if label >= 0:
                labels[idx] = find(int(label))

        # 2) attach noise points to the nearest (merged) centroid
        cents = cls._centroids(vectors, labels)
        if cents:
            keys = list(cents)
            matrix = np.stack([cents[k] for k in keys])
            for idx, label in enumerate(labels):
                if label >= 0:
                    continue
                sims = matrix @ vectors[idx]
                best = int(np.argmax(sims))
                if float(sims[best]) >= ATTACH_NOISE_COSINE:
                    labels[idx] = keys[best]
                    attached += 1

        if merged or attached:
            logger.info(f"Cluster repair: {merged} fragment merges, {attached} outlying reports attached")
        return labels
