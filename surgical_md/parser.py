"""Single-pass scanner that turns a Markdown source string into Selections."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Selection:
    kind: str  # heading_section | fenced_div | span | comment_section
    start: int
    end: int
    inner_start: int
    inner_end: int
    id: str | None = None
    classes: tuple[str, ...] = ()
    name: str | None = None
    level: int | None = None
    heading_text: str | None = None
    auto_id: bool = False  # True if id was derived from heading text


def slugify(text: str) -> str:
    """Pandoc-style auto-id: lowercase, strip formatting, spaces → hyphens.

    Conservative ASCII slug; non-ASCII letters are dropped. Returns 'section'
    if the result is empty.
    """
    s = text.strip().lower()
    # Strip basic inline-emphasis markers so '`code`' or '*bold*' don't
    # leak punctuation into the slug.
    s = re.sub(r"[`*_~]+", "", s)
    # Drop bracketed link / image markup, keep the link text.
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"\[([^\]]*)\]\[[^\]]*\]", r"\1", s)
    # Whitespace → hyphen.
    s = re.sub(r"\s+", "-", s)
    # Drop everything that isn't an allowed slug char.
    s = re.sub(r"[^a-z0-9_\-.]", "", s)
    # Collapse runs of hyphens left behind by stripped punctuation.
    s = re.sub(r"-+", "-", s)
    # Identifiers can't start with a digit or punctuation, and we trim trailing
    # punctuation too so 'foo---' doesn't become 'foo---'.
    s = re.sub(r"^[^a-z]+", "", s)
    s = re.sub(r"[^a-z0-9_]+$", "", s)
    return s or "section"


# A fenced code block: ``` or ~~~ opener through a matching closer of the same
# fence char and length. Imperfect (CommonMark allows >= length close), but
# adequate for keeping attribute-like text inside code from being parsed.
_FENCE_RE = re.compile(
    r"^(`{3,}|~{3,})[^\n]*\n.*?^\1[^\n]*$",
    re.MULTILINE | re.DOTALL,
)

_HEADING_RE = re.compile(
    r"^(#{1,6})[ \t]+(.+?)(?:[ \t]+\{([^}]*)\})?[ \t]*$",
    re.MULTILINE,
)

_DIV_OPEN_RE = re.compile(r"^(:{3,})[ \t]*\{([^}]*)\}[ \t]*$", re.MULTILINE)
_DIV_CLOSE_RE = re.compile(r"^(:{3,})[ \t]*$", re.MULTILINE)

_SPAN_RE = re.compile(r"\[([^\]\n]+)\]\{([^}\n]*)\}")

_SECTION_OPEN_RE = re.compile(r"<!--\s*SECTION:\s*([\w-]+)\s*-->")
_SECTION_CLOSE_RE = re.compile(r"<!--\s*END-SECTION:\s*([\w-]+)\s*-->")


def _find_code_fences(text: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in _FENCE_RE.finditer(text)]


def _in_ranges(pos: int, ranges: list[tuple[int, int]]) -> bool:
    for s, e in ranges:
        if s <= pos < e:
            return True
    return False


def _parse_attrs(s: str) -> tuple[str | None, tuple[str, ...]]:
    id_: str | None = None
    classes: list[str] = []
    for tok in s.split():
        if tok.startswith("#") and len(tok) > 1:
            id_ = tok[1:]  # last #id wins, per Pandoc
        elif tok.startswith(".") and len(tok) > 1:
            classes.append(tok[1:])
        # key=value attrs ignored in v1
    return id_, tuple(classes)


def _skip_leading_newline(text: str, i: int) -> int:
    if i < len(text) and text[i] == "\n":
        return i + 1
    return i


def _parse_headings(text: str, masked: list[tuple[int, int]]) -> list[Selection]:
    raw: list[
        tuple[re.Match[str], int, str | None, tuple[str, ...], str, bool]
    ] = []
    for m in _HEADING_RE.finditer(text):
        if _in_ranges(m.start(), masked):
            continue
        level = len(m.group(1))
        heading_text = m.group(2).strip()
        id_, classes = _parse_attrs(m.group(3) or "")
        auto = False
        if id_ is None:
            id_ = slugify(heading_text)
            auto = True
        raw.append((m, level, id_, classes, heading_text, auto))

    out: list[Selection] = []
    for i, (m, level, id_, classes, htext, auto) in enumerate(raw):
        end = len(text)
        for j in range(i + 1, len(raw)):
            m2, lvl2, _, _, _, _ = raw[j]
            if lvl2 <= level:
                end = m2.start()
                break
        inner_start = _skip_leading_newline(text, m.end())
        out.append(
            Selection(
                kind="heading_section",
                start=m.start(),
                end=end,
                inner_start=inner_start,
                inner_end=end,
                id=id_,
                classes=classes,
                level=level,
                heading_text=htext,
                auto_id=auto,
            )
        )
    return out


def _parse_fenced_divs(text: str, masked: list[tuple[int, int]]) -> list[Selection]:
    markers: list[tuple[str, re.Match[str]]] = []
    for m in _DIV_OPEN_RE.finditer(text):
        if not _in_ranges(m.start(), masked):
            markers.append(("open", m))
    for m in _DIV_CLOSE_RE.finditer(text):
        if _in_ranges(m.start(), masked):
            continue
        # Don't double-count an open as a close.
        if _DIV_OPEN_RE.match(text, m.start()):
            continue
        markers.append(("close", m))
    markers.sort(key=lambda x: x[1].start())

    stack: list[re.Match[str]] = []
    out: list[Selection] = []
    for kind, m in markers:
        if kind == "open":
            stack.append(m)
        else:
            if not stack:
                continue
            open_m = stack.pop()
            id_, classes = _parse_attrs(open_m.group(2))
            inner_start = _skip_leading_newline(text, open_m.end())
            inner_end = m.start()
            end = m.end()
            out.append(
                Selection(
                    kind="fenced_div",
                    start=open_m.start(),
                    end=end,
                    inner_start=inner_start,
                    inner_end=inner_end,
                    id=id_,
                    classes=classes,
                )
            )
    return out


def _parse_spans(text: str, masked: list[tuple[int, int]]) -> list[Selection]:
    out: list[Selection] = []
    for m in _SPAN_RE.finditer(text):
        if _in_ranges(m.start(), masked):
            continue
        id_, classes = _parse_attrs(m.group(2))
        if not id_ and not classes:
            continue  # plain `{...}` without id/class isn't an addressable span here
        inner_start = m.start() + 1
        inner_end = inner_start + len(m.group(1))
        out.append(
            Selection(
                kind="span",
                start=m.start(),
                end=m.end(),
                inner_start=inner_start,
                inner_end=inner_end,
                id=id_,
                classes=classes,
            )
        )
    return out


def _parse_comment_sections(
    text: str, masked: list[tuple[int, int]]
) -> list[Selection]:
    markers: list[tuple[str, str, re.Match[str]]] = []
    for m in _SECTION_OPEN_RE.finditer(text):
        if not _in_ranges(m.start(), masked):
            markers.append(("open", m.group(1), m))
    for m in _SECTION_CLOSE_RE.finditer(text):
        if not _in_ranges(m.start(), masked):
            markers.append(("close", m.group(1), m))
    markers.sort(key=lambda x: x[2].start())

    stack: list[tuple[str, re.Match[str]]] = []
    out: list[Selection] = []
    for kind, name, m in markers:
        if kind == "open":
            stack.append((name, m))
        else:
            for i in range(len(stack) - 1, -1, -1):
                if stack[i][0] == name:
                    _, open_m = stack.pop(i)
                    inner_start = _skip_leading_newline(text, open_m.end())
                    inner_end = m.start()
                    out.append(
                        Selection(
                            kind="comment_section",
                            start=open_m.start(),
                            end=m.end(),
                            inner_start=inner_start,
                            inner_end=inner_end,
                            name=name,
                        )
                    )
                    break
    return out


def parse_document(text: str) -> list[Selection]:
    masked = _find_code_fences(text)
    sels: list[Selection] = []
    sels.extend(_parse_headings(text, masked))
    sels.extend(_parse_fenced_divs(text, masked))
    sels.extend(_parse_spans(text, masked))
    sels.extend(_parse_comment_sections(text, masked))
    # Document order; at a tie, larger (containing) extents come first.
    sels.sort(key=lambda s: (s.start, -(s.end - s.start)))
    return sels
