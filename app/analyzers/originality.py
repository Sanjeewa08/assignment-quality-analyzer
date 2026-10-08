from difflib import SequenceMatcher
import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .text_utils import sentences


def analyze_originality(text, other_submissions=(), reference_text=""):
    text = text or ""
    sources = [
        {"label": label, "text": content}
        for label, content in other_submissions if content and content.strip()
    ]
    if reference_text and reference_text.strip():
        sources.append({"label": "provided reference text", "text": reference_text})

    sources = sources[:25]
    similarity_rows = []
    current_excerpt = (text or "")[:200_000]
    comparable_sources = [
        source for source in sources
        if re.search(r"(?u)\b\w\w+\b", source["text"][:50_000])
    ]
    if re.search(r"(?u)\b\w\w+\b", current_excerpt) and comparable_sources:
        corpus = [current_excerpt] + [source["text"][:50_000] for source in comparable_sources]
        matrix = TfidfVectorizer(
            ngram_range=(1, 2),
            min_df=1,
            max_features=100_000,
            stop_words=None,
        ).fit_transform(corpus)
        scores = cosine_similarity(matrix[0:1], matrix[1:]).flatten()
        for source, score in zip(comparable_sources, scores):
            similarity_rows.append({"source": source["label"], "similarity": round(float(score) * 100, 1)})

    current_sentences = sentences(text[:200_000])[:100]
    matches = []
    for sentence in current_sentences:
        if len(sentence) > 600:
            continue
        normalized = sentence.lower()
        if len(normalized.split()) < 6:
            continue
        for source in sources[:10]:
            for other in sentences(source["text"][:50_000])[:100]:
                if len(other) > 600:
                    continue
                ratio = SequenceMatcher(None, normalized, other.lower()).ratio()
                if ratio >= 0.76:
                    matches.append({
                        "sentence": sentence,
                        "source": source["label"],
                        "similarity": round(ratio * 100, 1),
                    })
                    break
            if matches and matches[-1]["sentence"] == sentence:
                break

    repeated_matches = len(matches)
    max_similarity = max((row["similarity"] for row in similarity_rows), default=0.0)
    score = max(0, round(100 - min(70, max_similarity * 0.7) - min(20, repeated_matches * 5)))
    return {
        "score": score,
        "breakdown": {
            "highest_document_similarity": max_similarity,
            "matched_sentences": repeated_matches,
            "compared_documents": len(sources),
            "sentence_comparison_documents": min(len(sources), 10),
            "similarity_available": bool(similarity_rows),
            "sources": similarity_rows,
        },
        "matches": matches[:20],
        "disclaimer": "Similarity flags are review leads, not plagiarism findings. Only this app's local submissions and any reference text you supplied were compared; the internet was not searched.",
    }
