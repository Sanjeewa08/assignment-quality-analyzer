import re


APA_AUTHOR_YEAR = re.compile(r"\(([^()]{1,100}?),\s*(?:19|20)\d{2}[a-z]?\)")
MLA_AUTHOR_PAGE = re.compile(r"\(([A-Z][A-Za-z'-]+)(?:\s+et al\.)?(?:\s+\d{1,4})?\)")


def analyze_citations(text):
    text = text or ""
    reference_heading = re.search(r"(?im)^\s*(references|works cited|bibliography)\s*$", text)
    if reference_heading:
        body, references = text[:reference_heading.start()], text[reference_heading.end():]
    else:
        body, references = text, ""
    apa = APA_AUTHOR_YEAR.findall(body)
    mla = [match.group(0) for match in MLA_AUTHOR_PAGE.finditer(body) if not re.search(r",\s*(?:19|20)\d{2}", match.group(0))]
    reference_entries = [
        line.strip() for line in references.splitlines()
        if line.strip() and not re.fullmatch(r"\s*\d+\s*", line)
    ]
    issues = []
    if (apa or mla) and not reference_heading:
        issues.append("In-text citations were found, but no references/Works Cited heading was detected.")
    if reference_heading and not reference_entries:
        issues.append("A reference-list heading is present, but no entries were detected beneath it.")
    if not apa and not mla and re.search(r"\b(according to|research shows|studies indicate|as reported by)\b", body, re.I):
        issues.append("The text contains source-like claims but no recognizable APA or MLA in-text citation.")
    if reference_entries and not any(re.search(r"\b(19|20)\d{2}\b", entry) for entry in reference_entries):
        issues.append("Reference entries do not appear to include a publication year.")
    detected_style = "APA" if apa else "MLA" if mla else "Not detected"
    suggestions = []
    if apa and not reference_heading:
        suggestions.append(
            "Add a References heading and a complete entry for each author-year citation; a basic APA entry is Author, A. A. (Year). Title. Source."
        )
    if mla and not reference_heading:
        suggestions.append(
            "Add a Works Cited heading and a complete entry for each author-page citation; a basic MLA entry is Author. Title. Publisher, Year."
        )
    if not apa and not mla:
        suggestions.append(
            "Check the required style guide; APA in-text citations commonly use (Author, Year), while MLA commonly uses (Author Page)."
        )
    return {
        "style_detected": detected_style,
        "apa_citations": len(apa),
        "mla_citations": len(mla),
        "in_text_count": len(apa) + len(mla),
        "has_reference_list": bool(reference_heading),
        "reference_heading": reference_heading.group(1) if reference_heading else None,
        "reference_count": len(reference_entries),
        "issues": issues,
        "suggestions": suggestions,
    }
