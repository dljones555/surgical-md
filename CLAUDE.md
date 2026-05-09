# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`surgical-md` is a Python CLI for **byte-exact, region-scoped edits to Markdown files**. It parses a `.md` source into addressable regions, lets you pull just one region's inner content out (e.g. for an LLM transform), and splices a replacement back in without touching surrounding bytes. See `README.md` for user-facing docs.

The tool is deliberately LLM-agnostic — model calls happen *outside* the tool over a stdio pipe.

## Architecture

Three files do all the work:

- **`surgical_md/parser.py`** — single-pass scanner. Code-fenced regions are masked first, then four kinds are extracted: `heading_section`, `fenced_div`, `span`, `comment_section`. Each becomes a `Selection(kind, id, classes, name, level, start, end, inner_start, inner_end)`. The `inner_*` offsets are what `replace_inner` splices into; `start`/`end` is the full extent including delimiters.
- **`surgical_md/selectors.py`** — `Document` wraps the source string + the parsed `Selection` list. Provides `select_by_id` / `select_by_class` / `select_by_section` / `select_by_regex` and `replace_inner`. The regex selector returns the *smallest containing region* per match — this is the bridge that makes "grep finds it, surgical edits it" work.
- **`surgical_md/cli.py`** — `argparse`-driven verbs: `list`, `show`, `replace`, `grep`. Selectors are mutually exclusive flags (`--id` / `--class` / `--section` / `--regex`); `replace` refuses to splice if a selector matches more than one region.

A heading-section runs from the heading line until the next heading of equal-or-higher level (or EOF). Fenced divs and `<!-- SECTION -->` markers nest via a stack; comment sections match opener and closer by name. Pandoc attribute syntax `{#id .class}` is parsed for `#id` and `.class` tokens; `key=value` attrs are ignored in v1.

## Commands

```bash
uv sync                                         # install deps incl. pytest
uv run pytest -q                                # run tests (13 covering all four kinds + round-trip)
uv run pytest tests/test_surgical_md.py::test_fenced_div   # one test
uv run python -m surgical_md list FILE          # exercise the CLI
```

`pyproject.toml` sets `tool.pytest.ini_options.pythonpath = ["."]` so tests import `surgical_md` without an editable install.

## Conventions

- Keep parser changes covered by a fixture-style test in `tests/test_surgical_md.py` — the round-trip test (`test_replace_inner_is_byte_exact_outside`) is the load-bearing invariant; do not regress byte-exactness outside the spliced region.
- New region kinds: add a `_parse_*` function in `parser.py`, append to `parse_document`, and extend `Document` selectors only if the new kind needs a new addressing scheme. The existing `select_by_id` / `select_by_class` / `select_by_regex` already handle anything carrying id/class.
- ATX headings only for now; setext (`===` / `---`) deferred.
