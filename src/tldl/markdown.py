import re
from datetime import datetime, timezone
from typing import Any

SENTENCE_MIN_WORDS = 20
SENTENCE_GAP_S = 0.7
PARAGRAPH_MAX_WORDS = 80
PARAGRAPH_GAP_S = 2.0
TIMESTAMP_INTERVAL_S = 300  # 5 minutes

_BRACKET_RE = re.compile(r"[\[\(][^\]\)]{0,40}[\]\)]")
_WS_RE = re.compile(r"\s+")
_SENTENCE_END_RE = re.compile(r"[.!?]['\"]?$")


def _clean(text: str) -> str:
    text = _BRACKET_RE.sub("", text)
    text = text.replace("\n", " ")
    text = _WS_RE.sub(" ", text).strip()
    return text


def _fmt_ts(seconds: float, *, force_hours: bool = False) -> str:
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h or force_hours:
        return f"{h}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"


def _yaml_str(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    s = str(value)
    if any(c in s for c in ':#"\n') or s != s.strip():
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return s


def _frontmatter(fields: dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in fields.items():
        if value is None or value == "":
            continue
        lines.append(f"{key}: {_yaml_str(value)}")
    lines.append("---")
    return "\n".join(lines)


def _coalesce_paragraphs(snippets: list[Any]) -> list[tuple[float, str]]:
    """
    Group raw caption snippets into (paragraph_start_seconds, paragraph_text) tuples.
    See heuristic in plan: sentence boundary on punctuation OR (>=20 words AND >=0.7s gap);
    paragraph break on >=80 words OR >=2.0s pause.
    """
    paragraphs: list[tuple[float, str]] = []
    para_words: list[str] = []
    para_start: float | None = None
    para_word_count = 0
    sentence_words: list[str] = []
    sentence_word_count = 0

    def flush_sentence() -> None:
        nonlocal sentence_words, sentence_word_count, para_word_count
        if not sentence_words:
            return
        para_words.extend(sentence_words)
        para_word_count += sentence_word_count
        sentence_words = []
        sentence_word_count = 0

    def flush_paragraph() -> None:
        nonlocal para_words, para_word_count, para_start
        flush_sentence()
        if para_words and para_start is not None:
            text = " ".join(para_words)
            text = text[0].upper() + text[1:] if text else text
            paragraphs.append((para_start, text))
        para_words = []
        para_word_count = 0
        para_start = None

    for i, snip in enumerate(snippets):
        text = _clean(snip.text)
        if not text:
            continue

        next_gap = 0.0
        if i + 1 < len(snippets):
            this_end = float(snip.start) + float(snip.duration)
            next_gap = max(0.0, float(snippets[i + 1].start) - this_end)

        # YouTube auto-captions use ">>" to mark speaker changes.
        # Treat each ">>" as a strong paragraph break.
        parts = [p.strip() for p in text.split(">>")]
        last_idx = len(parts) - 1

        for part_idx, part in enumerate(parts):
            if part_idx > 0:
                flush_paragraph()
            if not part:
                continue
            words = part.split()
            if not words:
                continue
            if para_start is None:
                para_start = float(snip.start)
            sentence_words.extend(words)
            sentence_word_count += len(words)

            # Gap-based heuristics only apply to the trailing part — the
            # gap belongs to the snippet boundary, not to internal splits.
            effective_gap = next_gap if part_idx == last_idx else 0.0
            ends_with_punct = bool(_SENTENCE_END_RE.search(part))
            force_sentence = (
                ends_with_punct
                or (sentence_word_count >= SENTENCE_MIN_WORDS and effective_gap >= SENTENCE_GAP_S)
                or (para_word_count + sentence_word_count >= PARAGRAPH_MAX_WORDS)
                or effective_gap >= PARAGRAPH_GAP_S
            )
            if force_sentence:
                flush_sentence()

            if para_word_count >= PARAGRAPH_MAX_WORDS or effective_gap >= PARAGRAPH_GAP_S:
                flush_paragraph()

    flush_paragraph()
    return paragraphs


def render_markdown(
    transcript: Any,
    metadata: dict[str, Any],
    source: dict[str, Any],
    *,
    include_timestamps: bool = False,
) -> str:
    """
    Build the markdown document from a FetchedTranscript + metadata + source info.
    """
    duration_s = metadata.get("duration") or 0
    use_hours = duration_s >= 3600
    duration_str = _fmt_ts(duration_s, force_hours=use_hours) if duration_s else None
    upload = metadata.get("upload_date")
    if upload and len(upload) == 8 and upload.isdigit():
        upload = f"{upload[0:4]}-{upload[4:6]}-{upload[6:8]}"

    fm: dict[str, Any] = {
        "title": metadata.get("title"),
        "channel": metadata.get("channel"),
        "source": source.get("kind"),
        "source_url": metadata.get("webpage_url"),
        "original_url": (
            source.get("original_url")
            if source.get("original_url") != metadata.get("webpage_url")
            else None
        ),
        "duration": duration_str,
        "upload_date": upload,
        "language": getattr(transcript, "language_code", None),
        "generated": getattr(transcript, "is_generated", None),
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    match = source.get("match")
    if match and "confidence" in match:
        fm["match_confidence"] = round(match["confidence"], 2)

    paragraphs = _coalesce_paragraphs(list(transcript.snippets))

    body_parts: list[str] = []
    title = metadata.get("title") or "Transcript"
    body_parts.append(f"# {title}")

    last_marker = -TIMESTAMP_INTERVAL_S
    for start, text in paragraphs:
        if include_timestamps and start >= last_marker + TIMESTAMP_INTERVAL_S:
            marker = (int(start) // TIMESTAMP_INTERVAL_S) * TIMESTAMP_INTERVAL_S
            body_parts.append(f"## [{_fmt_ts(marker, force_hours=use_hours)}]")
            last_marker = marker
        body_parts.append(text)

    return _frontmatter(fm) + "\n\n" + "\n\n".join(body_parts) + "\n"
