# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`surgical-md` is a Python CLI for **byte-exact, region-scoped edits to Markdown files**. It parses a `.md` source into addressable regions, lets you pull just one region's inner content out (e.g. for an LLM transform), and splices a replacement back in without touching surrounding bytes. See `README.md` for user-facing docs.

The tool is deliberately LLM-agnostic — model calls happen *outside* the tool over a stdio pipe.

## Architecture

Three files do all the work:

- **`surgical_md/parser.py`** — single-pass scanner. Code-fenced regions are masked first, then four kinds are extracted: `heading_section`, `fenced_div`, `span`, `comment_section`. Each becomes a `Selection(kind, id, classes, name, level, start, end, inner_start, inner_end)`. The `inner_*` offsets are what `replace_inner` splices into; `start`/`end` is the full extent including delimiters.
- **`surgical_md/selectors.py`** — `Document` wraps the source string + the parsed `Selection` list. Provides `select_by_id` / `select_by_class` / `select_by_section` / `select_by_heading_text` / `select_by_regex`, `replace_inner`, and `content_hash` (SHA-256 of the text, used for atomic-write coordination). The regex selector returns the *smallest containing region* per match — this is the bridge that makes "grep finds it, surgical edits it" work.
- **`surgical_md/cli.py`** — `argparse`-driven verbs: `list`, `show`, `replace`, `grep`, `hash`. Selectors are mutually exclusive flags (`--id` / `--class` / `--section` / `--regex`); `replace` refuses to splice if a selector matches more than one region. Filter-style I/O: `replace` reads new content from stdin by default, or from `-f PATH` / `--file PATH`. `-i` / `--in-place` writes back; `-n` / `--dry-run` prints a unified diff and writes nothing; `--expect-hash <sha>` makes the write atomic against concurrent edits. Errors go to stderr via the `_error(msg, code)` helper. Exit-code convention: `0` success, `1` no-match (grep), `2` cannot-proceed (ambiguous, hash mismatch, missing selector).

A heading-section runs from the heading line until the next heading of equal-or-higher level (or EOF). Headings without an explicit `{#id}` get an auto-id from `parser.slugify(heading_text)` (Pandoc-style); explicit ids always win. Fenced divs and `<!-- SECTION -->` markers nest via a stack; comment sections match opener and closer by name. Pandoc attribute syntax `{#id .class}` is parsed for `#id` and `.class` tokens; `key=value` attrs are ignored.

## Commands

```bash
uv sync                                                    # install deps + project (script entry)
uv run pytest -q                                           # full suite
uv run pytest tests/test_surgical_md.py::test_fenced_div   # one test
uv run surgical-md list FILE                               # exercise the CLI from a clone
```

End-user install (no PyPI release yet; install from the repo to keep the source auditable):

```bash
uv tool install git+https://github.com/dljones555/surgical-md
pipx install git+https://github.com/dljones555/surgical-md
```

`pyproject.toml` declares `[build-system]` (hatchling) and `[project.scripts]` so `surgical-md` installs as a real console entry point. `tool.pytest.ini_options.pythonpath = ["."]` keeps tests importing `surgical_md` directly without relying on the install.

## Conventions

- Keep parser changes covered by a fixture-style test in `tests/test_surgical_md.py` — the round-trip test (`test_replace_inner_is_byte_exact_outside`) is the load-bearing invariant; do not regress byte-exactness outside the spliced region.
- New region kinds: add a `_parse_*` function in `parser.py`, append to `parse_document`, and extend `Document` selectors only if the new kind needs a new addressing scheme. The existing `select_by_id` / `select_by_class` / `select_by_regex` already handle anything carrying id/class.
- ATX headings only for now; setext (`===` / `---`) deferred.
