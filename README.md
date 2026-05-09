# surgical-md

Surgical edits to Markdown for humans and AI agents. Address a specific
region of a `.md` file by id, class, named section, or heading text, hand it
to an LLM (or any transformer) over a pipe, and splice the result back in
place. Everything outside the selection is preserved byte-for-byte — this is
AST-style editing on the source text, not a re-render.

## Why

**Token economics.** Sending a 2,000-line `CLAUDE.md` to a model just to
tighten its "agent rules" section costs roughly 10× the tokens it should.
With `surgical-md` the model sees only the region you're editing — cheaper
inference, faster turnaround, and outputs that aren't diluted by unrelated
context.

**Bounded blast radius.** Whole-file LLM rewrites drift: tone shifts,
formatting changes, paragraphs you didn't ask to touch get "improved." When
the model only sees one named region, only that region can change. Bytes
outside the selection are guaranteed identical.

**Agent-friendly.** The `<!-- SECTION: name -->` markers are plain ASCII that
render to nothing — humans see clean prose, agents see addressable handles.
Combined with auto-IDs derived from heading text (Pandoc-style), most
existing markdown is addressable without retrofitting anchors.

## Addressing model

Three ways to point at a region. They compose — a regex match resolves to the
smallest enclosing id/class/section.

**1. Pandoc-style attributes on headings, fenced divs, and spans:**

```markdown
## Roadmap {#roadmap .draft}
The heading and everything beneath it (until the next heading of equal or
higher level) is the "heading section."

::: {#callout .warning}
A fenced div with an id and class.
:::

A paragraph with [a highlighted bit]{#hl .em} inline.
```

**2. HTML-comment section markers** for arbitrary regions that don't map to a
heading or div:

```markdown
<!-- SECTION: agent-rules -->
- be terse
- show diffs
<!-- END-SECTION: agent-rules -->
```

**3. Regex / grep**, which finds matches and returns the smallest containing
region from (1) or (2). Useful when you don't remember the id but you remember
a phrase.

Heading sections extend until the next heading of equal-or-higher level.
Fenced divs and comment sections nest. Attribute-shaped text inside fenced
code blocks is ignored.

## Install

Requires Python 3.12+. No PyPI release yet — install directly from the
repository (which lets you audit the source before running it):

```bash
# uv users (recommended)
uv tool install git+https://github.com/dljones555/surgical-md

# pipx users
pipx install git+https://github.com/dljones555/surgical-md

# from a local clone (for hacking on it)
git clone https://github.com/dljones555/surgical-md
cd surgical-md
uv sync     # installs deps + the surgical-md script
```

After install, `surgical-md` is on your PATH. (Inside a clone, prefix with
`uv run` if you haven't activated the venv.)

## Quick start

```bash
# pull a section out, transform it any way you like, splice it back
surgical-md show NOTES.md --section agent-rules \
  | your-llm "tighten this; keep the bullet style" \
  | surgical-md replace NOTES.md --section agent-rules -i
```

That's the whole loop. The model only sees the named region — that's the
token-savings win — and bytes outside the section are guaranteed unchanged.

## CLI

```bash
# enumerate selectable regions with line ranges and attrs
surgical-md list FILE

# print the inner content of a single region
surgical-md show FILE --id roadmap
surgical-md show FILE --class draft
surgical-md show FILE --section agent-rules
surgical-md show FILE --regex 'TODO\(\w+\)'

# splice new content (stdin by default; -i writes back; -n previews)
echo 'new body' | surgical-md replace FILE --id roadmap -i
surgical-md replace FILE --id roadmap -f new.md -i
surgical-md replace FILE --id roadmap -f new.md -n        # diff preview, no write

# atomic write: refuse to splice if the file changed since you last read it
HASH=$(surgical-md hash FILE)
... transform ...
surgical-md replace FILE --id roadmap -f new.md -i --expect-hash "$HASH"

# regex matches plus their containing region
surgical-md grep FILE 'pattern'

# sha256 of the document (use with --expect-hash)
surgical-md hash FILE
```

**Flags on `replace`:** `-f PATH` / `--file PATH` reads new content from a
file (default: stdin). `-i` / `--in-place` writes back to FILE (default:
stdout). `-n` / `--dry-run` prints a unified diff and writes nothing.
`--expect-hash SHA256` refuses to write unless the document's hash matches.

**Selectors are mutually exclusive:** pick one of `--id`, `--class`,
`--section`, or `--regex`. `replace` refuses ambiguous matches (more than
one region matched) so you can't silently edit the wrong place.

**Exit codes:** `0` success, `1` no match (grep convention), `2` cannot
proceed (ambiguous selector, hash mismatch, missing selector). Errors go
to stderr; data goes to stdout.

**Other flags:** `--version` / `-V`.

## The pipe pattern

The tool is deliberately LLM-agnostic. Wire any model CLI in over stdio:

```bash
HASH=$(surgical-md hash NOTES.md)
surgical-md show NOTES.md --section agent-rules \
  | claude -p "tighten these rules; keep the bullet style" \
  | surgical-md replace NOTES.md --section agent-rules -i --expect-hash "$HASH"
```

The model only sees the named region — that's the token-savings win.
`--expect-hash` makes the write atomic: if anything else touched the file
between `hash` and `replace`, the splice is refused rather than silently
clobbering a concurrent edit.

**PowerShell equivalent** (no `<<<` here-string operator; pipe instead):

```powershell
$hash = surgical-md hash NOTES.md
surgical-md show NOTES.md --section agent-rules `
  | your-llm "tighten this" `
  | surgical-md replace NOTES.md --section agent-rules -i --expect-hash $hash
```

## Library use

```python
from surgical_md import Document

doc = Document.from_file("NOTES.md")

# Select by section, id, class, regex, or heading text:
(sel,) = doc.select_by_section("agent-rules")
# alternatives:
#   doc.select_by_id("roadmap")
#   doc.select_by_class("draft")
#   doc.select_by_heading_text("Roadmap")
#   doc.select_by_heading_text("road", exact=False)
#   doc.select_by_regex(r"TODO\(\w+\)")

old = doc.get_inner(sel)
new_doc = doc.replace_inner(sel, transform(old))

# Atomic write pattern:
if new_doc.content_hash != doc.content_hash:
    open("NOTES.md", "w", encoding="utf-8").write(new_doc.text)
```

Selectors return `list[Selection]`. `Selection` carries `kind`, `id`,
`classes`, `name`, `level`, `heading_text`, `auto_id`, and the byte offsets
used by `replace_inner`. `Document.content_hash` is the SHA-256 of the
document text — useful for atomic-write coordination across processes.

## Tests

```bash
uv run pytest -q
```

## Scope

- ATX headings only (`#`…`######`); setext `===` / `---` deferred.
- Headings without an explicit `{#id}` get a Pandoc-style auto-id derived
  from the heading text (`## My Heading` → addressable as `--id my-heading`).
  Auto-IDs use ASCII-only slug rules; non-ASCII letters are dropped. Two
  headings with the same text resolve to the same auto-id and `replace`
  refuses the ambiguous match (a feature — fail loud, not silent).
- `[text](url){#id}` link attrs aren't recognized as a span — use a bare
  `[text]{#id}` span if you need to address it.
- Fenced-code masking treats the close fence as the same length as the open
  (CommonMark allows longer); fine in practice.
- `key=value` attributes in `{...}` are ignored; only `#id` and `.class` are
  parsed.

None of these affect the core select / splice loop.

## License

Licensed under the [Apache License, Version 2.0](LICENSE). See `NOTICE` for
attribution requirements; in short — keep the copyright + license intact in
forks and derivative works.

## Sponsor

If `surgical-md` saves you time, consider sponsoring continued development.
Funding links live in [`.github/FUNDING.yml`](.github/FUNDING.yml) (the
"Sponsor" button on the GitHub repo) — fill in the platforms you want to
accept and the button appears automatically.

Commercial use is welcome under Apache 2.0; if you'd like priority support,
custom features, or a private fork, get in touch.
