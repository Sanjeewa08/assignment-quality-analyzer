from app.analyzers.citations import analyze_citations
from app.analyzers.formatting import analyze_formatting
from app.analyzers.originality import analyze_originality
from app.analyzers.rubric import analyze_rubric, parse_rubric
from app.analyzers.writing import analyze_writing
from app.services.analysis import analyze_assignment


def test_writing_reports_counts_structure_and_readability():
    text = "Introduction\nA useful opening sentence explains the question.\n\nAnalysis\nThis body presents evidence clearly."
    result = analyze_writing(text)
    assert result["counts"]["words"] == 14
    assert result["counts"]["paragraphs"] == 2
    assert result["structure"]["sections"]["Introduction"]
    assert not result["structure"]["sections"]["Conclusion"]
    assert result["structure"]["section_word_counts"]["Introduction"] == 7
    assert result["structure"]["section_word_counts"]["Body"] == 5
    assert set(result["readability"]) == {
        "flesch_reading_ease", "flesch_kincaid_grade", "gunning_fog", "interpretation"
    }


def test_empty_and_non_english_writing_are_safe():
    empty = analyze_writing("")
    assert empty["counts"]["words"] == 0
    assert empty["readability"]["flesch_reading_ease"] == 0
    multilingual = analyze_writing("Introducción\nLa investigación analiza los resultados y presenta una conclusión.")
    assert multilingual["counts"]["words"] > 0
    assert multilingual["ai_likelihood"]["disclaimer"]


def test_writing_flags_common_errors_long_sentences_and_style():
    text = "Introduction " + ("This is a very long sentence with many details and ideas " * 7)
    text += " The result was recieved and teh conclusion was seperate. Moreover, moreover, furthermore."
    result = analyze_writing(text)
    assert result["grammar"]["errors"]
    assert result["style"]["long_sentences"]
    assert result["style"]["passive_voice_examples"]
    assert result["ai_likelihood"]["signals"]


def test_citation_detection_handles_apa_mla_and_missing_list():
    apa = analyze_citations("Research supports this (Smith, 2021).")
    assert apa["style_detected"] == "APA"
    assert not apa["has_reference_list"]
    assert apa["issues"]
    mla = analyze_citations("The finding is discussed (Smith 42).\n\nWorks Cited\nSmith. Book. 2020.")
    assert mla["style_detected"] == "MLA"
    assert mla["reference_count"] == 1


def test_reference_heading_without_entries_is_flagged():
    result = analyze_citations("A discussion.\n\nReferences")
    assert result["has_reference_list"]
    assert result["issues"]


def test_originality_compares_corpus_and_highlights_matching_sentence():
    sentence = "The careful review of evidence supports the central claim."
    result = analyze_originality(
        f"Introduction. {sentence} Conclusion.",
        [("another local submission", f"Background. {sentence} Results.")],
    )
    assert result["breakdown"]["highest_document_similarity"] > 0
    assert result["matches"][0]["sentence"] == sentence
    assert result["score"] < 100


def test_originality_empty_comparison_is_neutral_and_safe():
    result = analyze_originality("A short assignment.", [])
    assert result["score"] == 100
    assert result["breakdown"]["compared_documents"] == 0


def test_originality_handles_punctuation_only_comparison():
    result = analyze_originality("!!!", [("empty comparison", "???")])
    assert result["breakdown"]["similarity_available"] is False
    assert result["breakdown"]["highest_document_similarity"] == 0


def test_docx_formatting_checks_and_unavailable_formatting():
    unavailable = analyze_formatting()
    assert unavailable["available"] is False
    report = analyze_formatting({
        "font_names": ["Arial", "Arial"],
        "font_sizes": [12, 12],
        "heading_count": 2,
        "line_spacing": [1.0, 1.0],
        "margins": [{"top": 1.0, "bottom": 1.0, "left": 1.0, "right": 1.0}],
    })
    assert report["available"] is True
    assert report["score"] == 100


def test_formatting_flags_inconsistent_font_families():
    result = analyze_formatting({
        "font_names": ["Arial", "Times New Roman"],
        "heading_count": 1,
        "margins": [{"top": 1, "bottom": 1, "left": 1, "right": 1}],
    })
    assert result["score"] == 80
    assert not result["checks"][0]["passed"]


def test_rubric_parser_and_scorer_support_known_and_manual_criteria():
    criteria = parse_rubric("Must include a conclusion\nMin 100 words\nMin 3 references\nDiscuss evidence critically")
    assert [item["type"] for item in criteria] == ["section", "min_words", "min_references", "manual_review"]
    writing = analyze_writing("Introduction\nAnalysis\nConclusion")
    citations = analyze_citations("References\nSmith. 2020.")
    result = analyze_rubric(criteria, writing, citations)
    assert result["score"] == 33
    assert result["criteria"][-1]["passed"] is None


def test_assignment_service_produces_bounded_scores_feedback_and_highlights():
    text = "Introduction\n" + ("This is a sentence with a common phrase for testing. " * 8) + "\nConclusion"
    report = analyze_assignment(text, min_words=100, reference_text=text)
    assert 0 <= report["overall_score"] <= 100
    assert all(0 <= score <= 100 for score in report["category_scores"].values())
    assert report["feedback"]
    assert report["highlights"]
    assert "does not rewrite" in report["ethics"]


def test_rubric_word_count_and_reference_requirements_are_reported():
    report = analyze_assignment("Introduction. Conclusion.", min_words=20, min_references=2)
    assert not report["word_requirement"]["passed"]
    assert not report["reference_requirement"]["passed"]


def test_section_feedback_explains_why_revision_is_recommended():
    report = analyze_assignment("Introduction\nShort opening.\n\nConclusion\nBrief.")
    assert any("conclusion is brief because" in item.lower() for item in report["feedback"])
