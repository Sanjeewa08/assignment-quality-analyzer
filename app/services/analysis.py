from app.analyzers import (
    analyze_citations,
    analyze_formatting,
    analyze_originality,
    analyze_rubric,
    analyze_writing,
)
from app.analyzers.rubric import parse_rubric


def _category_score(value):
    return max(0, min(100, int(round(value))))


def analyze_assignment(
    text,
    formatting=None,
    min_words=None,
    max_words=None,
    other_submissions=(),
    reference_text="",
    rubric_criteria=None,
    min_references=None,
):
    writing = analyze_writing(text)
    citations = analyze_citations(text)
    originality = analyze_originality(text, other_submissions, reference_text)
    formatting_report = analyze_formatting(formatting)
    criteria = rubric_criteria if rubric_criteria is not None else parse_rubric("")
    rubric = analyze_rubric(criteria, writing, citations)
    counts = writing["counts"]

    count_score = 100
    if min_words and counts["words"] < min_words:
        count_score = max(0, round(counts["words"] / min_words * 100))
    if max_words and counts["words"] > max_words:
        count_score = min(count_score, max(0, round(max_words / counts["words"] * 100)))
    citation_score = 100 if citations["in_text_count"] and citations["has_reference_list"] else 55 if citations["in_text_count"] or citations["has_reference_list"] else 35
    if min_references:
        citation_score = min(citation_score, min(100, round(citations["reference_count"] / min_references * 100)))
    structure_score = round(sum(writing["structure"]["sections"].values()) / 3 * 100)
    readability_score = max(35, min(100, 100 - abs(writing["readability"]["flesch_kincaid_grade"] - 12) * 3))
    writing_score = round((readability_score + (100 if not writing["style"]["long_sentences"] else max(30, 100 - 10 * len(writing["style"]["long_sentences"]))) + (100 if not writing["grammar"]["errors"] else max(30, 100 - 8 * len(writing["grammar"]["errors"])))) / 3)
    format_score = formatting_report["score"] if formatting_report["available"] else 75
    rubric_score = rubric["score"] if rubric["score"] is not None else 75
    category_scores = {
        "Structure": structure_score,
        "Writing quality": writing_score,
        "Citations": citation_score,
        "Originality": originality["score"],
        "Formatting": format_score,
        "Requirements": min(count_score, rubric_score),
    }
    overall = round(sum(category_scores.values()) / len(category_scores))

    feedback = []
    missing = writing["structure"]["missing_sections"]
    if missing:
        feedback.append("Add a clearly labeled " + ", ".join(missing).lower() + " section.")
    section_counts = writing["structure"]["section_word_counts"]
    if "Introduction" in section_counts and section_counts["Introduction"] < 20:
        feedback.append(
            f"Your introduction is brief because it contains only {section_counts.get('Introduction', 0)} words; add context and state the question your assignment addresses."
        )
    if "Body" in section_counts and section_counts["Body"] < 50:
        feedback.append(
            f"Your body is brief because it contains only {section_counts.get('Body', 0)} words; develop your reasoning with relevant evidence and explain how it supports your point."
        )
    if "Conclusion" in section_counts and section_counts["Conclusion"] < 25:
        feedback.append(
            f"Your conclusion is brief because it contains only {section_counts['Conclusion']} words; try summarizing the main finding and its implication without introducing unsupported claims."
        )
    if min_words and counts["words"] < min_words:
        feedback.append(f"Your assignment is {min_words - counts['words']} words below the {min_words}-word minimum; develop the evidence or reasoning in the body.")
    if max_words and counts["words"] > max_words:
        feedback.append(f"Your assignment is {counts['words'] - max_words} words over the limit; remove repetition while keeping evidence and conclusions.")
    if writing["style"]["long_sentences"]:
        feedback.append("Review the longest sentences and split ideas where doing so improves clarity.")
    if not citations["has_reference_list"] or not citations["in_text_count"]:
        feedback.append("Check which claims need sources, then add matching in-text citations and a reference list in the required style.")
    if originality["matches"]:
        feedback.append("Review highlighted overlaps against the cited source; quote exact wording and attribute ideas accurately.")
    if writing["style"]["repeated_words"]:
        feedback.append("Check whether frequently repeated terms can be replaced with more precise wording without changing meaning.")
    for issue in citations["issues"]:
        if issue not in feedback:
            feedback.append(issue)
    if not feedback:
        feedback.append("The automated checks found no major baseline issues; proofread and compare the report with your assignment instructions.")

    highlights = []
    for sentence in writing["style"]["long_sentences"]:
        highlights.append({"text": sentence["text"], "type": "long sentence", "detail": f"{sentence['word_count']} words"})
    for match in originality["matches"]:
        highlights.append({"text": match["sentence"], "type": "possible overlap", "detail": f"{match['similarity']}% similarity to {match['source']}"})
    for error in writing["grammar"]["errors"]:
        highlights.append({"text": error["text"], "type": "possible spelling issue", "detail": f"Suggested: {error['suggestion']}"})

    report = {
        "overall_score": overall,
        "category_scores": category_scores,
        "writing": writing,
        "citations": citations,
        "originality": originality,
        "formatting": formatting_report,
        "rubric": rubric,
        "word_requirement": {
            "minimum": min_words,
            "maximum": max_words,
            "passed": (min_words is None or counts["words"] >= min_words) and (max_words is None or counts["words"] <= max_words),
        },
        "reference_requirement": {
            "minimum": min_references,
            "passed": min_references is None or citations["reference_count"] >= min_references,
        },
        "feedback": feedback,
        "highlights": highlights[:60],
        "ethics": "This report gives revision guidance only. It does not rewrite student work, determine misconduct, or establish who authored text.",
    }
    return report
