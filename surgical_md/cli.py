"""surgical-md CLI: list, show, replace, grep."""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path

from . import __version__
from .selectors import Document
from .parser import Selection


def _line(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def _attrs_str(s: Selection) -> str:
    parts: list[str] = []
    if s.id:
        parts.append(f"#{s.id}")
    parts.extend(f".{c}" for c in s.classes)
    if s.name:
        parts.append(f"name={s.name}")
    if s.level:
        parts.append(f"h{s.level}")
    return " ".join(parts) or "-"


def _select(doc: Document, args: argparse.Namespace) -> list[Selection]:
    chosen = [
        x for x in (args.id, args.cls, args.section, args.regex) if x is not None
    ]
    if len(chosen) != 1:
        raise SystemExit("specify exactly one of --id, --class, --section, --regex")
    if args.id is not None:
        return doc.select_by_id(args.id)
    if args.cls is not None:
        return doc.select_by_class(args.cls)
    if args.section is not None:
        return doc.select_by_section(args.section)
    return doc.select_by_regex(args.regex)


def cmd_list(args: argparse.Namespace) -> None:
    doc = Document.from_file(args.file)
    for s in doc.selections:
        a = _line(doc.text, s.start)
        b = _line(doc.text, max(s.start, s.end - 1))
        print(f"{s.kind:<16} L{a}-L{b:<4}  {_attrs_str(s)}")


def cmd_show(args: argparse.Namespace) -> None:
    doc = Document.from_file(args.file)
    sels = _select(doc, args)
    if not sels:
        raise SystemExit("no match")
    sep = ""
    for sel in sels:
        sys.stdout.write(sep)
        sys.stdout.write(doc.get_inner(sel))
        sep = "\n---\n"


def cmd_replace(args: argparse.Namespace) -> None:
    doc = Document.from_file(args.file)
    if args.expect_hash and doc.content_hash != args.expect_hash:
        raise SystemExit(
            f"hash mismatch: file is {doc.content_hash[:12]}, "
            f"expected {args.expect_hash[:12]}; refusing to write"
        )
    sels = _select(doc, args)
    if not sels:
        raise SystemExit("no match")
    if len(sels) > 1:
        raise SystemExit(
            f"selector matched {len(sels)} regions; refine to a single target"
        )
    sel = sels[0]
    if args.content is None:
        new = sys.stdin.read()
    else:
        new = Path(args.content).read_text(encoding="utf-8")
    new_doc = doc.replace_inner(sel, new)
    if args.dry_run:
        diff = difflib.unified_diff(
            doc.text.splitlines(keepends=True),
            new_doc.text.splitlines(keepends=True),
            fromfile=f"{args.file} (sha256:{doc.content_hash[:12]})",
            tofile=f"{args.file} (sha256:{new_doc.content_hash[:12]})",
        )
        sys.stdout.writelines(diff)
        return
    if args.in_place:
        Path(args.file).write_text(new_doc.text, encoding="utf-8")
    else:
        sys.stdout.write(new_doc.text)


def cmd_grep(args: argparse.Namespace) -> None:
    doc = Document.from_file(args.file)
    sels = doc.select_by_regex(args.pattern)
    for sel in sels:
        line = _line(doc.text, sel.start)
        print(f"{args.file}:{line}: {sel.kind} {_attrs_str(sel)}")


def cmd_hash(args: argparse.Namespace) -> None:
    doc = Document.from_file(args.file)
    print(doc.content_hash)


def _add_selector_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--id", help="select by id")
    p.add_argument("--class", dest="cls", help="select by class")
    p.add_argument("--section", help="select by SECTION name")
    p.add_argument("--regex", help="select by regex (smallest containing region)")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="surgical-md")
    p.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"surgical-md {__version__}",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("list", help="enumerate selectable regions")
    pl.add_argument("file")
    pl.set_defaults(func=cmd_list)

    ps = sub.add_parser("show", help="print inner content of a selection")
    ps.add_argument("file")
    _add_selector_args(ps)
    ps.set_defaults(func=cmd_show)

    pr = sub.add_parser("replace", help="replace inner content of a selection")
    pr.add_argument("file")
    _add_selector_args(pr)
    pr.add_argument(
        "-f",
        "--file",
        dest="content",
        default=None,
        help="path to new content (default: read stdin)",
    )
    pr.add_argument(
        "-i",
        "--in-place",
        dest="in_place",
        action="store_true",
        help="write back to FILE instead of stdout",
    )
    pr.add_argument(
        "-n",
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="print a unified diff of what would change; do not write",
    )
    pr.add_argument(
        "--expect-hash",
        dest="expect_hash",
        default=None,
        help="refuse to write unless the file's sha256 matches this value",
    )
    pr.set_defaults(func=cmd_replace)

    pg = sub.add_parser(
        "grep",
        help="find regex matches with their containing selection",
    )
    pg.add_argument("file")
    pg.add_argument("pattern")
    pg.set_defaults(func=cmd_grep)

    ph = sub.add_parser(
        "hash",
        help="print sha256 of the document (use with replace --expect-hash)",
    )
    ph.add_argument("file")
    ph.set_defaults(func=cmd_hash)

    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
