"""Document — selectors and inner-text replacement."""

from __future__ import annotations

import re
from pathlib import Path

from .parser import Selection, parse_document


class Document:
    def __init__(self, text: str):
        self.text = text
        self.selections: list[Selection] = parse_document(text)

    @classmethod
    def from_file(cls, path: str | Path) -> "Document":
        return cls(Path(path).read_text(encoding="utf-8"))

    def select_by_id(self, id_: str) -> list[Selection]:
        return [s for s in self.selections if s.id == id_]

    def select_by_class(self, cls: str) -> list[Selection]:
        return [s for s in self.selections if cls in s.classes]

    def select_by_section(self, name: str) -> list[Selection]:
        return [
            s
            for s in self.selections
            if s.kind == "comment_section" and s.name == name
        ]

    def select_by_regex(
        self, pattern: str, flags: int = 0, kind: str | None = None
    ) -> list[Selection]:
        """Find regex matches and return the smallest selection containing each.

        `kind` optionally restricts which selection kinds are eligible (e.g.
        only `comment_section`). A match outside any selection is ignored.
        """
        regex = re.compile(pattern, flags)
        eligible = [
            s for s in self.selections if kind is None or s.kind == kind
        ]
        seen: set[Selection] = set()
        out: list[Selection] = []
        for m in regex.finditer(self.text):
            containing = [
                s for s in eligible if s.start <= m.start() and m.end() <= s.end
            ]
            if not containing:
                continue
            smallest = min(containing, key=lambda s: s.end - s.start)
            if smallest not in seen:
                seen.add(smallest)
                out.append(smallest)
        return out

    def get_inner(self, sel: Selection) -> str:
        return self.text[sel.inner_start : sel.inner_end]

    def replace_inner(self, sel: Selection, new_text: str) -> "Document":
        new_full = (
            self.text[: sel.inner_start] + new_text + self.text[sel.inner_end :]
        )
        return Document(new_full)
