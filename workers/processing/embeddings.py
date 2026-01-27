from __future__ import annotations

import math
import os
import re
import unicodedata
from typing import Iterable, Sequence

from openai import OpenAI

from workers.config import Config


def normalize(text: str) -> str:
    """Normalize text for comparison: lowercase, remove accents, clean legal terms."""
    text = text.lower()
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")

    # German legal cleanup
    text = re.sub(r"§\s*\d+[a-zA-Z]*", " paragraph ", text)
    text = re.sub(r"\b(vob/a|vob/b|uvg|gwb)\b", " vergaberecht ", text)

    text = re.sub(r"\s+", " ", text).strip()
    return text


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
    # Award & evaluation
    "Zuschlagskriterien und deren Gewichtung gemäß Vergabeunterlagen",
    "Bewertung der Angebote nach Preis und Qualität",
    "Wertung der Angebote nach VOB/A",

    # Penalties & contract risks
    "Vertragsstrafen bei Fristüberschreitung oder Leistungsstörungen",
    "Sanktionen bei Nichteinhaltung vertraglicher Pflichten",

    # Labour & compliance
    "Tariftreueerklärung und Mindestentgelt gemäß geltendem Tarifrecht",
    "Verpflichtung zur Einhaltung von Mindestlohnvorschriften",

    # Data protection
    "Datenschutz und Verarbeitung personenbezogener Daten gemäß DSGVO",
    "Auftragsverarbeitung und Vertraulichkeit",

    # Deadlines
    "Frist zur Angebotsabgabe und Schlusstermin",
    "Abgabefrist für Angebote einschließlich Uhrzeit",

    # Variants
    "Zulässigkeit von Nebenangeboten oder Alternativangeboten",
    "Bedingungen für Variantenangebote",

    # Eligibility
    "Eignungsnachweise, Referenzen und Formblätter",
    "Nachweise zur technischen und wirtschaftlichen Leistungsfähigkeit",

    # Execution
    "Ausführungsbeginn, Bauzeit und Leistungsfristen",
    "Zeitplan für die Ausführung der Leistungen",

    # Economics
    "Wirtschaftlichkeit der Angebote und Preisprüfung",
    "Prüfung ungewöhnlich niedriger Angebote",

    # Risks
    "Vertragsrisiken, Haftung und Gewährleistung"
]


    keyword_terms = [
    # Award
    "zuschlagskriterien", "wertung", "gewichtung", "bewertungsmatrix",

    # Contract penalties
    "vertragsstrafe", "vertragsstrafen", "pönale", "sanktion",

    # Labour law
    "tariftreue", "mindestentgelt", "mindestlohn", "tarifvertrag",

    # Data protection
    "dsgvo", "datenschutz", "auftragsverarbeitung", "vertraulichkeit",

    # Deadlines
    "abgabefrist", "angebotsfrist", "schlusstermin", "einreichungsfrist",

    # Variants
    "nebenangebot", "alternativangebot", "variante",

    # Eligibility
    "formblatt", "eignung", "nachweis", "referenz", "präqualifikation",

    # Execution
    "ausführungsbeginn", "leistungsbeginn", "bauzeit", "fertigstellung",

    # Economics
    "wirtschaftlichkeit", "preisprüfung", "angebotspreis",
    "ungewöhnlich niedriges angebot",

    # Risk
    "haftung", "vertragsrisiko", "gewährleistung", "mängel"
]


    topic_terms = {

    # ─────────────────────────────────────────
    # AWARD & EVALUATION
    # ─────────────────────────────────────────
    "zuschlag": {
        "positive": [
            "zuschlagskriterien",
            "bewertungskriterien",
            "wertung",
            "gewichtung",
            "bewertungsmatrix",
            "zuschlagsentscheidung",
            "angebotspunktzahl",
            "preis gewichtung",
            "qualitaetsbewertung"
        ],
        "negative": [
            "angebotspreis",
            "rechnungsbetrag",
            "abschlagszahlung"
        ]
    },

    # ─────────────────────────────────────────
    # CONTRACT PENALTIES & SANCTIONS
    # ─────────────────────────────────────────
    "vertragsstrafe": {
        "positive": [
            "vertragsstrafe",
            "vertragsstrafen",
            "pönale",
            "sanktion",
            "verzugsschaden",
            "fristueberschreitung",
            "terminueberschreitung"
        ],
        "negative": [
            "schadensersatz allgemein",
            "haftung allgemein"
        ]
    },

    # ─────────────────────────────────────────
    # LABOUR LAW / TARIFF COMPLIANCE
    # ─────────────────────────────────────────
    "tariftreue": {
        "positive": [
            "tariftreue",
            "tariftreueerklaerung",
            "mindestentgelt",
            "mindestlohn",
            "tarifvertrag",
            "entgeltregelung",
            "lohnbindung"
        ],
        "negative": [
            "angebotspreis",
            "kalkulation"
        ]
    },

    # ─────────────────────────────────────────
    # DATA PROTECTION / GDPR
    # ─────────────────────────────────────────
    "datenschutz": {
        "positive": [
            "dsgvo",
            "datenschutz",
            "datenverarbeitung",
            "personenbezogene daten",
            "auftragsverarbeitung",
            "vertraulichkeit",
            "datensicherheit"
        ],
        "negative": [
            "betriebsgeheimnis ohne personenbezogene daten"
        ]
    },

    # ─────────────────────────────────────────
    # SUBMISSION DEADLINES (CRITICAL)
    # ─────────────────────────────────────────
    "fristen": {
        "positive": [
            "abgabefrist",
            "angebotsfrist",
            "schlusstermin",
            "frist zur angebotsabgabe",
            "eingang der angebote",
            "abgabedatum"
        ],
        "negative": [
            "ausfuehrungsbeginn",
            "bauzeit",
            "leistungsbeginn",
            "fertigstellung",
            "veroeffentlichungsdatum"
        ]
    },

    # ─────────────────────────────────────────
    # VARIANTS / ALTERNATIVE OFFERS
    # ─────────────────────────────────────────
    "nebenangebote": {
        "positive": [
            "nebenangebot",
            "nebenangebote",
            "alternativangebot",
            "alternativangebote",
            "variante",
            "variantenangebote"
        ],
        "negative": [
            "hauptangebot",
            "grundangebot"
        ]
    },

    # ─────────────────────────────────────────
    # ELIGIBILITY / SUITABILITY
    # ─────────────────────────────────────────
    "eignung": {
        "positive": [
            "eignung",
            "eignungsnachweis",
            "eignungskriterien",
            "nachweise",
            "referenzen",
            "präqualifikation",
            "formblatt",
            "selbstauskunft"
        ],
        "negative": [
            "leistungsbeschreibung",
            "ausfuehrungsdetails"
        ]
    },

    # ─────────────────────────────────────────
    # EXECUTION PERIOD / CONSTRUCTION TIME
    # ─────────────────────────────────────────
    "ausfuehrung": {
        "positive": [
            "ausfuehrungsbeginn",
            "leistungsbeginn",
            "bauzeit",
            "ausfuehrungsfrist",
            "fertigstellung",
            "ausfuehrungszeitraum"
        ],
        "negative": [
            "abgabefrist",
            "angebotsfrist",
            "schlusstermin"
        ]
    },

    # ─────────────────────────────────────────
    # ECONOMIC EVALUATION / PRICE CHECK
    # ─────────────────────────────────────────
    "wirtschaftlichkeit": {
        "positive": [
            "wirtschaftlichkeit",
            "preispruefung",
            "angebotspreis",
            "kalkulation",
            "kostenstruktur",
            "ungewoehnlich niedriges angebot",
            "preisangemessenheit"
        ],
        "negative": [
            "abschlagszahlung",
            "schlussrechnung"
        ]
    },

    # ─────────────────────────────────────────
    # RISKS / LIABILITY
    # ─────────────────────────────────────────
    "risiken": {
        "positive": [
            "risiko",
            "vertragsrisiko",
            "haftung",
            "gewaehrleistung",
            "maengel",
            "schadensersatz",
            "haftungsumfang"
        ],
        "negative": [
            "allgemeine hinweise ohne verpflichtung"
        ]
    },

    # ─────────────────────────────────────────
    # CERTIFICATES / APPROVALS
    # ─────────────────────────────────────────
    "zertifikate": {
        "positive": [
            "zertifikat",
            "zertifizierung",
            "iso",
            "qualitaetsmanagement",
            "sicherheitszertifikat",
            "nachweis der zertifizierung"
        ],
        "negative": [
            "herstellerangaben ohne nachweis"
        ]
    },

    # ─────────────────────────────────────────
    # SAFETY / OCCUPATIONAL HEALTH
    # ─────────────────────────────────────────
    "sicherheit": {
        "positive": [
            "arbeitssicherheit",
            "sicherheitsvorschriften",
            "gesundheitsschutz",
            "gefaehrdungsbeurteilung",
            "schutzmassnahmen",
            "baustellensicherheit"
        ],
        "negative": [
            "allgemeine empfehlungen"
        ]
    },

    # ─────────────────────────────────────────
    # CONTRACTUAL TERMS
    # ─────────────────────────────────────────
    "vertrag": {
        "positive": [
            "vertragsbedingungen",
            "besondere vertragsbedingungen",
            "agb",
            "vob/b",
            "vertragsbestandteil"
        ],
        "negative": [
            "leistungsbeschreibung ohne rechtswirkung"
        ]
    }
}

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
            for topic, term_dict in topic_terms.items():
                # Handle new structure with positive/negative terms
                positive_terms = term_dict.get("positive", [])
                if any(term in lowered for term in positive_terms):
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
