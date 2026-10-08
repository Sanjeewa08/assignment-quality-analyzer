import re


WORD_PATTERN = re.compile(r"\b[\w'-]+\b", re.UNICODE)
SECTION_NAMES = {
    "introduction": "Introduction",
    "background": "Introduction",
    "methodology": "Body",
    "methods": "Body",
    "main discussion": "Body",
    "analysis": "Body",
    "findings": "Body",
    "results": "Body",
    "discussion": "Body",
    "conclusion": "Conclusion",
    "summary": "Conclusion",
    "recommendations": "Conclusion",
    "references": None,
    "works cited": None,
    "bibliography": None,
}


def words(text):
    return WORD_PATTERN.findall((text or "").lower())


def sentences(text):
    return [
        item.strip() for item in re.split(r"(?<=[.!?])\s+|\n+", (text or "").strip())
        if item.strip()
    ]


def paragraphs(text):
    return [item.strip() for item in re.split(r"\n\s*\n", (text or "").strip()) if item.strip()]


def headings(text):
    found = []
    for line in (text or "").splitlines():
        candidate = line.strip()
        if candidate and len(candidate) <= 100 and (
            candidate.isupper()
            or re.match(r"^(?:\d+(?:\.\d+)*\.?\s+)?(?:introduction|background|methodology|methods|results|discussion|analysis|conclusion|references|bibliography)\b", candidate, re.I)
        ):
            found.append(candidate)
    return found


def section_word_counts(text):
    counts = {}
    active_section = None
    for line in (text or "").splitlines():
        heading = re.fullmatch(
            r"\s*(?:\d+(?:\.\d+)*\.?\s*)?([A-Za-z][A-Za-z ]{1,40}):?\s*",
            line,
        )
        section = SECTION_NAMES.get(heading.group(1).strip().lower()) if heading else None
        if heading and heading.group(1).strip().lower() in SECTION_NAMES:
            active_section = section
            if active_section:
                counts.setdefault(active_section, 0)
            continue
        if active_section:
            counts[active_section] = counts.get(active_section, 0) + len(words(line))
    return counts
