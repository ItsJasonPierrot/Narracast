"""Text cleanup utilities — pure regex, no new dependencies."""

import re


def normalize_whitespace(text: str) -> str:
    """Collapse runs of spaces/tabs; normalise line endings; strip trailing spaces."""
    # Normalise CRLF / CR to LF
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Strip trailing whitespace on every line
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    # Collapse runs of blank lines to at most two (one paragraph break)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Collapse inline runs of spaces/tabs to a single space
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def fix_hyphenated_line_breaks(text: str) -> str:
    """Re-join words split by a hyphen at the end of a line.

    "inter-\\nesting" → "interesting"
    Handles both hard-hyphen splits (word- \\n word) and soft-hyphen (u+00AD).
    """
    # Hard hyphen at end of line followed by the continuation word
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    # Soft hyphen (U+00AD)
    text = re.sub(r"(\w)­\n(\w)", r"\1\2", text)
    return text


def remove_page_numbers(text: str) -> str:
    """Remove common page-number patterns.

    Handles:
    - Lines that are purely a number (possibly surrounded by whitespace)
    - Lines like "Page 12", "— 12 —", "- 12 -", "12 of 345"
    """
    patterns = [
        r"^[ \t]*\d+[ \t]*$",                      # bare number
        r"^[ \t]*[Pp]age\.?\s+\d+[ \t]*$",         # "Page 12"
        r"^[ \t]*[-–—]+\s*\d+\s*[-–—]+[ \t]*$",    # "— 12 —"
        r"^[ \t]*\d+\s+of\s+\d+[ \t]*$",           # "12 of 345"
    ]
    combined = re.compile("|".join(patterns), re.MULTILINE)
    return combined.sub("", text)


def strip_urls(text: str) -> str:
    """Remove http/https/www URLs from the text."""
    # Match URLs (greedy up to whitespace)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"www\.\S+", "", text)
    return text


def remove_repeated_pdf_headers_footers(text: str) -> str:
    """Remove lines repeated across many PDF pages.

    This is intentionally conservative: it only runs when page breaks are
    present and removes short repeated lines that appear on at least three
    pages and at least half of all pages.
    """
    pages = text.replace("\r\n", "\n").replace("\r", "\n").split("\f")
    pages = [page for page in pages if page.strip()]
    if len(pages) < 3:
        return text

    counts: dict[str, int] = {}
    originals: dict[str, str] = {}
    for page in pages:
        seen_on_page = set()
        for line in page.split("\n"):
            normalized = re.sub(r"\s+", " ", line.strip())
            if not normalized or len(normalized) > 90:
                continue
            key = normalized.lower()
            if key in seen_on_page:
                continue
            seen_on_page.add(key)
            counts[key] = counts.get(key, 0) + 1
            originals.setdefault(key, normalized)

    threshold = max(3, (len(pages) + 1) // 2)
    repeated = {key for key, count in counts.items() if count >= threshold}
    if not repeated:
        return text

    cleaned_pages = []
    for page in pages:
        kept = []
        for line in page.split("\n"):
            key = re.sub(r"\s+", " ", line.strip()).lower()
            if key and key in repeated:
                continue
            kept.append(line)
        cleaned_pages.append("\n".join(kept))
    return "\n\f\n".join(cleaned_pages)


def fix_pdf_line_wraps(text: str) -> str:
    """Join PDF line wraps that split sentences across physical lines."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    result: list[str] = []

    def _should_join(left: str, right: str) -> bool:
        left_s = left.strip()
        right_s = right.strip()
        if not left_s or not right_s:
            return False
        if re.match(r"^(chapter|part|section)\b", left_s, re.IGNORECASE):
            return False
        if left_s.endswith((".", "!", "?", ":", ";", "”", '"', ")")):
            return False
        if re.match(r"^([#*•-]|\d+[.)])\s+", right_s):
            return False
        if re.match(r"^(chapter|part|section)\b", right_s, re.IGNORECASE):
            return False
        if right_s.isupper() and len(right_s.split()) <= 8:
            return False
        return True

    for line in lines:
        if result and _should_join(result[-1], line):
            result[-1] = result[-1].rstrip() + " " + line.strip()
        else:
            result.append(line)
    return "\n".join(result)


def clean_pdf_text(text: str) -> str:
    """Conservative PDF-oriented cleanup pipeline."""
    text = fix_hyphenated_line_breaks(text)
    text = remove_repeated_pdf_headers_footers(text)
    text = remove_page_numbers(text)
    text = fix_pdf_line_wraps(text)
    text = strip_urls(text)
    return normalize_whitespace(text)


def apply_all(text: str) -> str:
    """Run all cleanup steps in the recommended order."""
    text = fix_hyphenated_line_breaks(text)
    text = remove_page_numbers(text)
    text = strip_urls(text)
    text = normalize_whitespace(text)
    return text
