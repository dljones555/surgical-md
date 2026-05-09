import io
import sys

import pytest

from surgical_md import Document
from surgical_md.cli import build_parser
from surgical_md.parser import slugify


def test_heading_with_id_and_class():
    text = "# Title {#main .intro}\nbody content\n"
    doc = Document(text)
    sels = doc.select_by_id("main")
    assert len(sels) == 1
    assert sels[0].kind == "heading_section"
    assert "intro" in sels[0].classes
    assert doc.get_inner(sels[0]) == "body content\n"


def test_heading_section_extent_stops_at_equal_level():
    text = "# A {#a}\nA body\n# B {#b}\nB body\n"
    doc = Document(text)
    a = doc.select_by_id("a")[0]
    assert doc.get_inner(a) == "A body\n"


def test_subheading_does_not_close_parent():
    text = "# A {#a}\ntop\n## A1\nsub body\n# B {#b}\nB body\n"
    doc = Document(text)
    a = doc.select_by_id("a")[0]
    inner = doc.get_inner(a)
    assert "top" in inner
    assert "sub body" in inner
    assert "B body" not in inner


def test_comment_section():
    text = (
        "before\n"
        "<!-- SECTION: rules -->\n"
        "rule 1\n"
        "rule 2\n"
        "<!-- END-SECTION: rules -->\n"
        "after\n"
    )
    doc = Document(text)
    sels = doc.select_by_section("rules")
    assert len(sels) == 1
    assert doc.get_inner(sels[0]) == "rule 1\nrule 2\n"


def test_fenced_div():
    text = "before\n::: {#note .warning}\ninside\n:::\nafter\n"
    doc = Document(text)
    sels = doc.select_by_id("note")
    assert len(sels) == 1
    assert sels[0].kind == "fenced_div"
    assert "warning" in sels[0].classes
    assert doc.get_inner(sels[0]) == "inside\n"


def test_span():
    text = "Some [highlighted text]{#hl .em} word.\n"
    doc = Document(text)
    sels = doc.select_by_id("hl")
    assert len(sels) == 1
    assert sels[0].kind == "span"
    assert doc.get_inner(sels[0]) == "highlighted text"


def test_select_by_class_multiple_hits():
    text = "# A {.foo}\na\n# B {.foo .bar}\nb\n"
    doc = Document(text)
    assert len(doc.select_by_class("foo")) == 2
    assert len(doc.select_by_class("bar")) == 1


def test_replace_inner_is_byte_exact_outside():
    text = "preamble\n# A {#a}\nold body\n# B {#b}\nB body\n"
    doc = Document(text)
    a = doc.select_by_id("a")[0]
    new = doc.replace_inner(a, "new body\n")
    assert new.text == "preamble\n# A {#a}\nnew body\n# B {#b}\nB body\n"


def test_replace_comment_section_keeps_markers():
    text = "<!-- SECTION: x -->\nold\n<!-- END-SECTION: x -->\n"
    doc = Document(text)
    sel = doc.select_by_section("x")[0]
    new = doc.replace_inner(sel, "fresh\n")
    assert new.text == "<!-- SECTION: x -->\nfresh\n<!-- END-SECTION: x -->\n"


def test_code_fence_masks_attributes_inside():
    text = "# Real {#real}\nbody\n```\n# Fake {#fake}\n```\nafter\n"
    doc = Document(text)
    assert doc.select_by_id("real")
    assert not doc.select_by_id("fake")


def test_select_by_regex_returns_smallest_containing():
    text = "# Outer {#outer}\nbefore\n::: {#inner}\nfind me here\n:::\nafter\n"
    doc = Document(text)
    sels = doc.select_by_regex(r"find me")
    assert len(sels) == 1
    assert sels[0].id == "inner"


def test_nested_comment_sections():
    text = (
        "<!-- SECTION: outer -->\n"
        "<!-- SECTION: inner -->\n"
        "x\n"
        "<!-- END-SECTION: inner -->\n"
        "<!-- END-SECTION: outer -->\n"
    )
    doc = Document(text)
    inner = doc.select_by_section("inner")
    outer = doc.select_by_section("outer")
    assert len(inner) == 1 and len(outer) == 1
    assert doc.get_inner(inner[0]) == "x\n"
    assert "<!-- SECTION: inner -->" in doc.get_inner(outer[0])


def test_slugify_basic():
    assert slugify("My Heading") == "my-heading"
    assert slugify("Hello, World!") == "hello-world"
    assert slugify("API & Auth") == "api-auth"


def test_slugify_strips_leading_non_letters():
    assert slugify("1. First Section") == "first-section"
    assert slugify("---weird---") == "weird"


def test_slugify_strips_inline_emphasis_and_links():
    assert slugify("`code` heading") == "code-heading"
    assert slugify("*bold* and _italic_") == "bold-and-italic"
    assert slugify("See [the docs](http://x)") == "see-the-docs"


def test_slugify_empty_falls_back():
    assert slugify("") == "section"
    assert slugify("!!!") == "section"


def test_heading_without_explicit_id_gets_auto_id():
    text = "# My Heading\nbody\n"
    doc = Document(text)
    sels = doc.select_by_id("my-heading")
    assert len(sels) == 1
    assert sels[0].auto_id is True
    assert sels[0].heading_text == "My Heading"
    assert doc.get_inner(sels[0]) == "body\n"


def test_explicit_id_overrides_auto_id():
    text = "# My Heading {#custom}\nbody\n"
    doc = Document(text)
    assert doc.select_by_id("custom")
    assert not doc.select_by_id("my-heading")
    sel = doc.select_by_id("custom")[0]
    assert sel.auto_id is False
    assert sel.heading_text == "My Heading"


def test_select_by_heading_text_exact():
    text = "# Intro\nbody\n## Notes\nnotes\n# Refs\nrefs\n"
    doc = Document(text)
    sels = doc.select_by_heading_text("Notes")
    assert len(sels) == 1
    assert sels[0].level == 2
    assert doc.get_inner(sels[0]) == "notes\n"


def test_select_by_heading_text_substring_case_insensitive():
    text = "# Project Roadmap {#r}\nplans\n## Other\nx\n"
    doc = Document(text)
    sels = doc.select_by_heading_text("road", exact=False)
    assert len(sels) == 1
    assert sels[0].id == "r"


def test_select_by_heading_text_strips_attr_block():
    text = "# Intro {#i .top}\nbody\n"
    doc = Document(text)
    sels = doc.select_by_heading_text("Intro")
    assert len(sels) == 1
    assert sels[0].id == "i"


def test_content_hash_changes_with_text():
    a = Document("# A {#a}\nold\n")
    b = Document("# A {#a}\nnew\n")
    assert a.content_hash != b.content_hash
    # Stable for the same input.
    assert a.content_hash == Document("# A {#a}\nold\n").content_hash


def test_content_hash_unchanged_after_no_op_replace():
    text = "# A {#a}\nbody\n"
    doc = Document(text)
    sel = doc.select_by_id("a")[0]
    same = doc.replace_inner(sel, doc.get_inner(sel))
    assert same.content_hash == doc.content_hash


def _run_cli(argv, stdin_text=""):
    """Invoke the CLI as if from the shell.

    Returns (stdout, stderr, exit_code). Captures both streams so tests can
    assert that errors land on stderr and data lands on stdout.
    """
    parser = build_parser()
    old_stdin, old_stdout, old_stderr = sys.stdin, sys.stdout, sys.stderr
    sys.stdin = io.StringIO(stdin_text)
    sys.stdout = io.StringIO()
    sys.stderr = io.StringIO()
    code = 0
    try:
        args = parser.parse_args(argv)
        args.func(args)
    except SystemExit as e:
        if e.code is None:
            code = 0
        elif isinstance(e.code, int):
            code = e.code
        else:
            # SystemExit("string") would normally print to stderr at top level;
            # mimic that here so tests can inspect the message.
            print(str(e.code), file=sys.stderr)
            code = 1
    out = sys.stdout.getvalue()
    err = sys.stderr.getvalue()
    sys.stdin, sys.stdout, sys.stderr = old_stdin, old_stdout, old_stderr
    return out, err, code


def test_replace_expect_hash_blocks_on_mismatch(tmp_path):
    f = tmp_path / "doc.md"
    f.write_text("# A {#a}\nold\n", encoding="utf-8")
    out, err, code = _run_cli(
        [
            "replace",
            str(f),
            "--id",
            "a",
            "--in-place",
            "--expect-hash",
            "0" * 64,
        ],
        stdin_text="new\n",
    )
    assert code != 0
    assert f.read_text(encoding="utf-8") == "# A {#a}\nold\n"


def test_replace_expect_hash_allows_on_match(tmp_path):
    f = tmp_path / "doc.md"
    f.write_text("# A {#a}\nold\n", encoding="utf-8")
    expected = Document.from_file(f).content_hash
    out, err, code = _run_cli(
        [
            "replace",
            str(f),
            "--id",
            "a",
            "--in-place",
            "--expect-hash",
            expected,
        ],
        stdin_text="new\n",
    )
    assert code == 0
    assert f.read_text(encoding="utf-8") == "# A {#a}\nnew\n"


def test_replace_reads_from_file_flag(tmp_path):
    doc = tmp_path / "doc.md"
    doc.write_text("# A {#a}\nold\n", encoding="utf-8")
    src = tmp_path / "new.md"
    src.write_text("from-file body\n", encoding="utf-8")
    out, err, code = _run_cli(
        ["replace", str(doc), "--id", "a", "--file", str(src), "--in-place"],
    )
    assert code == 0
    assert doc.read_text(encoding="utf-8") == "# A {#a}\nfrom-file body\n"


def test_show_no_match_exits_1_with_stderr_message(tmp_path):
    f = tmp_path / "doc.md"
    f.write_text("# A {#a}\nbody\n", encoding="utf-8")
    out, err, code = _run_cli(["show", str(f), "--id", "nope"])
    assert code == 1
    assert "no match" in err
    assert out == ""  # no data on stdout


def test_replace_hash_mismatch_exits_2_with_stderr_message(tmp_path):
    f = tmp_path / "doc.md"
    f.write_text("# A {#a}\nold\n", encoding="utf-8")
    out, err, code = _run_cli(
        ["replace", str(f), "--id", "a", "-i", "--expect-hash", "0" * 64],
        stdin_text="new\n",
    )
    assert code == 2
    assert "hash mismatch" in err
    assert out == ""


def test_replace_ambiguous_selector_exits_2(tmp_path):
    f = tmp_path / "doc.md"
    f.write_text("# A {.shared}\na\n# B {.shared}\nb\n", encoding="utf-8")
    out, err, code = _run_cli(
        ["replace", str(f), "--class", "shared", "-i"],
        stdin_text="new\n",
    )
    assert code == 2
    assert "matched 2 regions" in err
    assert out == ""


def test_no_selector_exits_2(tmp_path):
    f = tmp_path / "doc.md"
    f.write_text("# A {#a}\nbody\n", encoding="utf-8")
    out, err, code = _run_cli(["show", str(f)])
    assert code == 2
    assert "specify exactly one" in err


def test_version_flag_prints_and_exits_zero(capsys):
    """argparse 'version' action exits with code 0 after printing."""
    parser = build_parser()
    code = 0
    try:
        parser.parse_args(["--version"])
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 1
    captured = capsys.readouterr()
    assert code == 0
    assert "surgical-md" in captured.out
    assert "0.2.0" in captured.out


def test_replace_short_flags(tmp_path):
    """-i for --in-place, -n for --dry-run, -f for --file."""
    doc = tmp_path / "doc.md"
    doc.write_text("# A {#a}\nold\n", encoding="utf-8")
    src = tmp_path / "new.md"
    src.write_text("short-flag body\n", encoding="utf-8")
    out, err, code = _run_cli(
        ["replace", str(doc), "--id", "a", "-f", str(src), "-i", "-n"],
    )
    assert code == 0
    # -n should suppress the write even though -i is set.
    assert doc.read_text(encoding="utf-8") == "# A {#a}\nold\n"
    assert out.startswith("---")


def test_replace_dry_run_emits_diff_and_does_not_write(tmp_path):
    f = tmp_path / "doc.md"
    f.write_text("# A {#a}\nold\n", encoding="utf-8")
    out, err, code = _run_cli(
        ["replace", str(f), "--id", "a", "--in-place", "--dry-run"],
        stdin_text="new\n",
    )
    assert code == 0
    # File untouched.
    assert f.read_text(encoding="utf-8") == "# A {#a}\nold\n"
    # Diff present and shaped like a unified diff.
    assert out.startswith("---")
    assert "-old" in out
    assert "+new" in out


def test_full_round_trip_on_sample():
    text = (
        "# Intro {#intro .top}\n"
        "intro body\n"
        "## Notes\n"
        "notes body\n"
        "# Refs {#refs}\n"
        "<!-- SECTION: cite -->\n"
        "[1] something\n"
        "<!-- END-SECTION: cite -->\n"
    )
    doc = Document(text)
    cite = doc.select_by_section("cite")[0]
    out = doc.replace_inner(cite, "[1] something else\n").text
    assert out == text.replace("[1] something\n", "[1] something else\n")
