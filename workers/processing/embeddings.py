from __future__ import annotations

import math
import os
from typing import Iterable, Sequence

from openai import OpenAI

from workers.config import Config


def _cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _embed_texts(client: OpenAI, model: str, texts: Iterable[str]) -> list[list[float]]:
    response = client.embeddings.create(
        model=model,
        input=list(texts),
    )
    return [item.embedding for item in response.data]


def select_relevant_chunks(
    chunks: list[str],
    query: str,
    config: Config,
    logger,
    doc_id: str,
    source_filename: str,
    top_k: int | None = None,
) -> list[str] | None:
    """Return top-k most relevant chunks (preserving original order).

    Returns None to indicate fallback to original chunk list.
    """
    enable = os.environ.get("ENABLE_EMBEDDINGS", "false").lower() in ("true", "1", "yes")
    if not enable:
        return None
    if not chunks:
        return None
    if not config.openai_api_key or config.openai_api_key == "your_openai_api_key_here":
        return None

    model = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
    if top_k is None:
        try:
            top_k = int(os.environ.get("EMBEDDINGS_TOP_K", "8"))
        except ValueError:
            top_k = 8
    top_k = max(1, min(top_k, len(chunks)))

    multi_queries = [
        "Zuschlagskriterien und Bewertungskriterien",
        "Vertragsstrafe, Vertragsstrafen, Sanktionen",
        "Tariftreue, Mindestentgelt, Lohn",
        "Datenschutz, DSGVO, Datenverarbeitung",
        "Fristen, Abgabefrist, Angebotsfrist, Termine",
        "Nebenangebote, Alternativangebote, Varianten",
        "Formblatt, Eignung, Nachweise, Referenzen",
        "Ausführungsbeginn, Bauzeit, Leistungsbeginn",
        "Wirtschaftlichkeit, Kosten, Preisprüfung",
        "Risiken, Haftung, Vertragsrisiko",
    ]

    keyword_terms = [
        "Zuschlagskriterien",
        "Vertragsstrafe",
        "Tariftreue",
        "Mindestentgelt",
        "DSGVO",
        "Nebenangebote",
        "Formblatt",
        "Eignung",
        "Abgabefrist",
        "Angebotsfrist",
        "Ausführungsbeginn",
        "Bauzeit",
        "Wirtschaftlichkeit",
        "Preisprüfung",
        "Zertifikat",
        "Zertifizierung",
        "Risiko",
    ]

    topic_terms = {
        "zuschlag": ["zuschlagskriterien", "bewertungskriterien", "wertung"],
        "vertragsstrafe": ["vertragsstrafe", "vertragsstrafen", "sanktion"],
        "tariftreue": ["tariftreue", "mindestentgelt", "tarif"],
        "datenschutz": ["dsgvo", "datenschutz", "datenverarbeitung"],
        "fristen": ["frist", "abgabefrist", "angebotsfrist", "termin"],
        "nebenangebote": ["nebenangebot", "alternativangebot", "variante"],
        "eignung": ["formblatt", "eignung", "nachweis", "referenz"],
        "ausfuehrung": ["ausführungsbeginn", "leistungsbeginn", "bauzeit", "ausführung"],
        "wirtschaftlichkeit": ["wirtschaftlichkeit", "kosten", "preisprüfung", "preis"],
        "risiken": ["risiko", "haftung", "vertragsrisiko"],
    }

    def normalize(text: str) -> str:
        return text.lower()

    try:
        client = OpenAI(api_key=config.openai_api_key)
        chunk_embeddings = _embed_texts(client, model, chunks)

        # Multi-query embedding search
        query_embeddings = _embed_texts(client, model, multi_queries)
        candidate_scores: dict[int, float] = {}
        for q_idx, q_emb in enumerate(query_embeddings):
            scores = [
                _cosine_similarity(q_emb, chunk_emb)
                for chunk_emb in chunk_embeddings
            ]
            top_indices = sorted(
                range(len(scores)),
                key=lambda i: scores[i],
                reverse=True,
            )[:3]
            for i in top_indices:
                candidate_scores[i] = max(candidate_scores.get(i, 0.0), scores[i])

        # Hybrid keyword recall
        keyword_candidates = set()
        for i, chunk in enumerate(chunks):
            lower = normalize(chunk)
            if any(term.lower() in lower for term in keyword_terms):
                keyword_candidates.add(i)

        candidate_indices = set(candidate_scores.keys()) | keyword_candidates
        if not candidate_indices:
            return None

        # Build candidate list with metadata
        candidates = []
        for i in candidate_indices:
            candidates.append(
                {
                    "index": i,
                    "text": chunks[i],
                    "score": candidate_scores.get(i, 0.0),
                    "embedding": chunk_embeddings[i],
                    "source_document": source_filename,
                }
            )

        # Drop near-duplicates among candidates
        candidates_sorted = sorted(candidates, key=lambda c: c["score"], reverse=True)
        deduped = []
        for cand in candidates_sorted:
            if any(
                _cosine_similarity(cand["embedding"], kept["embedding"]) > 0.92
                for kept in deduped
            ):
                continue
            deduped.append(cand)

        # Rerank: maximize coverage of topics, keep deterministic scoring
        def coverage_score(text: str) -> set[str]:
            lowered = normalize(text)
            covered = set()
            for topic, terms in topic_terms.items():
                if any(term in lowered for term in terms):
                    covered.add(topic)
            return covered

        for cand in deduped:
            cand["coverage"] = coverage_score(cand["text"])

        top_candidates = sorted(deduped, key=lambda c: c["score"], reverse=True)[:25]
        selected = []
        covered_topics: set[str] = set()

        # Apply diversity constraint only when multiple sources exist
        sources_present = {c["source_document"] for c in top_candidates}
        source_limits = {}

        while top_candidates and len(selected) < top_k:
            best = None
            best_gain = -1
            for cand in top_candidates:
                if len(sources_present) > 1:
                    count = source_limits.get(cand["source_document"], 0)
                    if count >= 3:
                        continue
                gain = len(cand["coverage"] - covered_topics)
                # Tie-breaker: higher embedding score
                if gain > best_gain or (gain == best_gain and cand["score"] > (best["score"] if best else -1)):
                    best = cand
                    best_gain = gain
            if not best:
                break
            selected.append(best)
            covered_topics |= best["coverage"]
            source_limits[best["source_document"]] = source_limits.get(best["source_document"], 0) + 1
            top_candidates.remove(best)

        if not selected:
            return None

        selected_indices = sorted([c["index"] for c in selected])
        selected_chunks = [chunks[i] for i in selected_indices]

        coverage_counts = {topic: 0 for topic in topic_terms}
        for cand in selected:
            for topic in cand["coverage"]:
                coverage_counts[topic] += 1

        logger.debug(
            "[Embeddings] doc_id=%s (%s) num_chunks=%d candidates=%d selected=%d coverage=%s",
            doc_id,
            source_filename,
            len(chunks),
            len(candidate_indices),
            len(selected_chunks),
            coverage_counts,
        )

        return selected_chunks
    except Exception as exc:  # noqa: BLE001
        logger.debug(
            "[Embeddings] Failed for doc_id=%s (%s): %s",
            doc_id,
            source_filename,
            exc,
        )
        return None
