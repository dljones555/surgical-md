# surgical-md

Surgical edits to Markdown. Address a specific region of a `.md` file by id,
class, or named section, hand it to an LLM (or any transformer) over a pipe,
and splice the result back in place. Everything outside the selection is
preserved byte-for-byte — this is AST-style editing on the source text, not a
re-render.

## Why

Whole-file LLM rewrites have unintended side effects on content beyond your intent changes. Adjusting this can be a back-and-forth effort with multiple prompting turns or require manual editing. If you can name *just* the region you
care about, the model only sees that region and only that region changes.

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

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

## CLI

Run via `uv run python -m surgical_md`.

```bash
# enumerate selectable regions with line ranges and attrs
uv run python -m surgical_md list FILE

# print the inner content of a single region
uv run python -m surgical_md show  FILE --id roadmap
uv run python -m surgical_md show  FILE --class draft
uv run python -m surgical_md show  FILE --section agent-rules
uv run python -m surgical_md show  FILE --regex 'TODO\(\w+\)'

# splice new content into a region (markers/headings preserved)
uv run python -m surgical_md replace FILE --id roadmap --from new.md --in-place
cat new.md | uv run python -m surgical_md replace FILE --id roadmap --from -

# regex matches plus their containing region
uv run python -m surgical_md grep FILE 'pattern'
```

`replace` refuses ambiguous selectors: if your `--class` or `--regex` matches
more than one region, refine to a single target. Without `--in-place` the
modified document is written to stdout.

## The pipe pattern

The tool is deliberately LLM-agnostic. Wire any model CLI in over stdio:

```bash
surgical-md show NOTES.md --section agent-rules \
  | claude -p "tighten these rules; keep the bullet style" \
  | surgical-md replace NOTES.md --section agent-rules --from - --in-place
```

The model only sees the named region. Everything outside it is preserved
exactly.

## Library use

```python
from surgical_md import Document

doc = Document.from_file("NOTES.md")

(sel,) = doc.select_by_section("agent-rules")
old = doc.get_inner(sel)

new_doc = doc.replace_inner(sel, transform(old))
open("NOTES.md", "w", encoding="utf-8").write(new_doc.text)
```

Selectors return `list[Selection]`; `Selection` carries `kind`, `id`,
`classes`, `name`, `level`, and the byte offsets used by `replace_inner`.

## Tests

```bash
uv run pytest -q
```

## Scope (v1)

- ATX headings only (`#`…`######`); setext `===` / `---` deferred.
- `[text](url){#id}` link attrs aren't recognized as a span — for v1 use a
  bare `[text]{#id}` span if you need to address it.
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
