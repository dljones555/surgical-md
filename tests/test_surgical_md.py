from surgical_md import Document


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
