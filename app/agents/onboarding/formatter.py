from __future__ import annotations

import re


def format_brief(text: str, max_sentences: int = 3, max_paragraph_chars: int = 120) -> str:
    if not text:
        return ""

    normalized = text.strip()

    sentences = re.split(r"(?<=[.!?])\s+", normalized)
    sentences = [s.strip() for s in sentences if s.strip()]
    if len(sentences) > max_sentences:
        sentences = sentences[:max_sentences]
    trimmed = " ".join(sentences)

    paragraphs = [p.strip() for p in trimmed.split("\n\n") if p.strip()]

    def wrap_para(p: str) -> str:
        if len(p) <= max_paragraph_chars:
            return p
        words = p.split()
        lines: list[str] = []
        current: list[str] = []
        cur_len = 0
        for w in words:
            if cur_len + (1 if current else 0) + len(w) > max_paragraph_chars:
                lines.append(" ".join(current))
                current = [w]
                cur_len = len(w)
            else:
                if current:
                    cur_len += 1 + len(w)
                    current.append(w)
                else:
                    current = [w]
                    cur_len = len(w)
        if current:
            lines.append(" ".join(current))
        return "\n".join(lines)

    wrapped = "\n\n".join(wrap_para(p) for p in paragraphs) if paragraphs else trimmed
    return wrapped
