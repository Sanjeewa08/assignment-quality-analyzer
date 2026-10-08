import os
import re
import statistics
from collections import Counter

import textstat

from .text_utils import headings, paragraphs, section_word_counts, sentences, words


COMMON_MISSPELLINGS = {
    "teh": "the",
    "recieve": "receive",
    "seperate": "separate",
    "definately": "definitely",
    "occured": "occurred",
    "wich": "which",
    "begining": "beginning",
}
PASSIVE_PATTERN = re.compile(
    r"\b(?:am|is|are|was|were|be|been|being|get|got)\s+(?:\w+ed|known|written|seen|made|taken|given|found|built|done|shown)\b",
    re.I,
)
FORMULAIC_TRANSITIONS = re.compile(r"\b(moreover|furthermore|in conclusion|it is important to note)\b", re.I)


def _readability(text, word_count, sentence_count):
    if not word_count or not sentence_count:
        return {
            "flesch_reading_ease": 0.0,
            "flesch_kincaid_grade": 0.0,
            "gunning_fog": 0.0,
            "interpretation": "Add complete sentences to estimate readability.",
        }
    try:
        flesch = round(textstat.flesch_reading_ease(text), 1)
        grade = round(textstat.flesch_kincaid_grade(text), 1)
        fog = round(textstat.gunning_fog(text), 1)
        interpretation = (
            "Very easy to read" if flesch >= 80 else
            "Plain and accessible" if flesch >= 60 else
            "Moderately complex" if flesch >= 30 else
            "Dense; consider shorter sentences and clearer wording"
        )
    except (ValueError, ZeroDivisionError):
        flesch, grade, fog = 0.0, 0.0, 0.0
        interpretation = "Readability formulas could not score this language reliably."
    return {
        "flesch_reading_ease": flesch,
        "flesch_kincaid_grade": grade,
        "gunning_fog": fog,
        "interpretation": interpretation,
    }


def _grammar(text):
    errors = [
        {"text": match.group(0), "suggestion": COMMON_MISSPELLINGS[match.group(0).lower()], "type": "spelling"}
        for match in re.finditer(r"\b(?:" + "|".join(COMMON_MISSPELLINGS) + r")\b", text, re.I)
    ]
    double_spaces = len(re.findall(r"(?<!\n) {2,}", text))
    punctuation = len(re.findall(r"\s+[,.!?;:]", text))
    if os.environ.get("AQA_LANGUAGE_TOOL", "").lower() == "true":
        try:
            import language_tool_python

            with language_tool_python.LanguageTool("en-US") as tool:
                for match in tool.check(text):
                    errors.append({
                        "text": text[match.offset:match.offset + match.errorLength],
                        "suggestion": match.replacements[0] if match.replacements else "",
                        "type": match.ruleIssueType,
                        "message": match.message,
                    })
            engine = "LanguageTool (local)"
        except (ImportError, OSError, RuntimeError) as exc:
            return {
                "errors": errors,
                "double_spaces": double_spaces,
                "spacing_flags": punctuation,
                "engine": "local spelling and spacing rules",
                "language_tool_error": str(exc),
            }
    else:
        engine = "local spelling and spacing rules"
    return {
        "errors": errors,
        "double_spaces": double_spaces,
        "spacing_flags": punctuation,
        "engine": engine,
    }


def analyze_writing(text):
    text = text or ""
    word_list = words(text)
    sentence_list = sentences(text)
    paragraph_list = paragraphs(text)
    count = len(word_list)
    sentence_count = len(sentence_list)
    lengths = [len(words(sentence)) for sentence in sentence_list]
    counts = Counter(word_list)
    repeated = [
        {"word": word, "count": amount}
        for word, amount in counts.most_common(10)
        if amount >= 4 and len(word) > 3
    ]
    passive_matches = [match.group(0) for match in PASSIVE_PATTERN.finditer(text)]
    long_sentences = [
        {"text": sentence, "word_count": length}
        for sentence, length in zip(sentence_list, lengths) if length > 35
    ]
    unique = len(set(word_list))
    diversity = round(unique / count, 3) if count else 0.0
    sentence_variance = round(statistics.pvariance(lengths), 2) if len(lengths) > 1 else 0.0

    section_map = {
        "Introduction": bool(re.search(r"\b(introduction|background)\b", text, re.I)),
        "Body": bool(re.search(r"\b(methodology|methods|main discussion|analysis|findings|results|discussion)\b", text, re.I)),
        "Conclusion": bool(re.search(r"\b(conclusion|summary|recommendations?)\b", text, re.I)),
    }
    detected_headings = headings(text)
    section_counts = section_word_counts(text)
    readability = _readability(text, count, sentence_count)
    formulaic = len(FORMULAIC_TRANSITIONS.findall(text))
    ai_signals = []
    if len(lengths) >= 5 and sentence_variance < 10:
        ai_signals.append("sentence lengths show low variation")
    if formulaic >= 3:
        ai_signals.append("frequent formulaic transitions")
    if count >= 80 and diversity < 0.35:
        ai_signals.append("low vocabulary diversity")
    if len(repeated) >= 3:
        ai_signals.append("several frequently repeated words")
    confidence = min(95, len(ai_signals) * 20)
    style = (
        "Formal or academic" if formulaic or len(passive_matches) / max(sentence_count, 1) > 0.1
        else "Conversational or neutral"
    )
    return {
        "counts": {
            "words": count,
            "characters": len(text),
            "characters_without_spaces": len(re.sub(r"\s", "", text)),
            "sentences": sentence_count,
            "paragraphs": len(paragraph_list),
        },
        "readability": readability,
        "structure": {
            "sections": section_map,
            "missing_sections": [name for name, present in section_map.items() if not present],
            "headings": detected_headings,
            "section_word_counts": section_counts,
        },
        "grammar": _grammar(text),
        "style": {
            "average_sentence_words": round(statistics.mean(lengths), 1) if lengths else 0,
            "long_sentences": long_sentences,
            "passive_voice_examples": passive_matches[:10],
            "repeated_words": repeated,
            "vocabulary_diversity": diversity,
            "tone": style,
        },
        "ai_likelihood": {
            "score": confidence,
            "confidence": confidence,
            "signals": ai_signals,
            "disclaimer": "This uncalibrated heuristic is not a reliable authorship test or a probability. It cannot prove that text was written by AI or by a person; do not use it for disciplinary decisions.",
        },
    }
