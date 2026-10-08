import re


def parse_rubric(text):
    criteria = []
    for raw in (text or "").splitlines():
        line = raw.strip().lstrip("-* ").strip()
        if not line:
            continue
        words = re.search(r"\bmin(?:imum)?\s+(\d+)\s+words?\b", line, re.I)
        references = re.search(r"\bmin(?:imum)?\s+(\d+)\s+references?\b", line, re.I)
        section = re.search(r"\b(?:must include|requires?)\s+(an?\s+)?(introduction|body|conclusion)\b", line, re.I)
        if words:
            criterion = {"label": line, "type": "min_words", "value": int(words.group(1))}
        elif references:
            criterion = {"label": line, "type": "min_references", "value": int(references.group(1))}
        elif section:
            criterion = {"label": line, "type": "section", "value": section.group(2).capitalize()}
        else:
            criterion = {"label": line, "type": "manual_review", "value": None}
        criteria.append(criterion)
    return criteria


def analyze_rubric(criteria, writing, citations):
    results = []
    for criterion in criteria or []:
        kind = criterion.get("type")
        value = criterion.get("value")
        if kind == "min_words":
            actual = writing["counts"]["words"]
            passed = actual >= value
            detail = f"{actual} words; at least {value} required."
        elif kind == "min_references":
            actual = citations["reference_count"]
            passed = actual >= value
            detail = f"{actual} references detected; at least {value} required."
        elif kind == "section":
            passed = writing["structure"]["sections"].get(value, False)
            detail = f"{value} section {'detected' if passed else 'not detected'}."
        else:
            passed = None
            detail = "This criterion needs lecturer review and is not automatically scored."
        results.append({
            "label": criterion.get("label", "Rubric criterion"),
            "type": kind,
            "passed": passed,
            "detail": detail,
        })
    scored = [row for row in results if row["passed"] is not None]
    score = round(sum(row["passed"] for row in scored) / len(scored) * 100) if scored else None
    return {"criteria": results, "score": score, "scored_count": len(scored)}
