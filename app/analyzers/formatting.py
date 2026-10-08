def analyze_formatting(formatting=None):
    formatting = formatting or {}
    if not formatting:
        return {
            "available": False,
            "score": None,
            "checks": [],
            "note": "Formatting details are available for DOCX files only.",
        }
    checks = []
    fonts = formatting.get("font_names", [])
    distinct_fonts = {font for font in fonts if font}
    checks.append({
        "name": "Consistent font family",
        "passed": len(distinct_fonts) <= 1,
        "detail": f"{len(distinct_fonts)} distinct font family/families detected." if distinct_fonts else "Font family is inherited from document styles.",
    })
    sizes = formatting.get("font_sizes", [])
    checks.append({
        "name": "Consistent font size",
        "passed": not sizes or max(sizes) - min(sizes) <= 1.5,
        "detail": f"{len(set(round(size, 1) for size in sizes))} distinct body/run font sizes detected." if sizes else "Font sizes are not explicitly set in the document.",
    })
    headings = formatting.get("heading_count", 0)
    checks.append({
        "name": "Heading styles",
        "passed": headings > 0,
        "detail": f"{headings} styled heading(s) detected." if headings else "No built-in Word heading styles detected.",
    })
    spacings = formatting.get("line_spacing", [])
    normalized = [float(value) for value in spacings if isinstance(value, (int, float))]
    checks.append({
        "name": "Consistent line spacing",
        "passed": not normalized or max(normalized) - min(normalized) <= 0.15,
        "detail": "Line spacing is consistent or inherited from styles." if not normalized or max(normalized) - min(normalized) <= 0.15 else "Line spacing varies between paragraphs.",
    })
    margins = formatting.get("margins", [])
    margins_valid = all(
        all(value is None or 0.5 <= value <= 2.0 for value in section.values())
        for section in margins
    )
    checks.append({
        "name": "Page margins",
        "passed": margins_valid,
        "detail": "Margins fall within a typical 0.5–2 inch range." if margins_valid else "One or more margins are outside a typical 0.5–2 inch range.",
    })
    passed = sum(check["passed"] for check in checks)
    return {
        "available": True,
        "score": round(passed / len(checks) * 100),
        "checks": checks,
        "note": "Formatting requirements vary by institution; verify against your assignment brief.",
    }
