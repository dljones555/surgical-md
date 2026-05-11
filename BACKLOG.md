# Backlog

Decided + ranked. **Now** is small and definite. **Next** is the v0.3 bet to
pick. **Ideas** are post-v0.3 directions worth keeping but not yet committed.

## Now (small, definite)

- **Tag `v0.2.0`** on the current commit. `pyproject.toml` already declares
  `version = "0.2.0"`; no git tag exists yet.
- **Atomic writes: tempfile + `os.replace`.** Today `replace -i` writes
  directly to the target. A crash mid-write can truncate the file. Pattern
  is: write next to the target, fsync, `os.replace` over the original.
  Closes the "atomic-write story is more aspirational than the docs admit"
  critique.
- **README: document the recommended pattern.** Full file as context →
  constrained region output → deterministic splice. (Shipped with the
  README rewrite that introduced this file.)

## Next — pick one v0.3 bet

Both are real wins; doing both at once muddies what v0.3 *is*.

- **`--validate` flag** — re-parse post-splice and refuse if the new
  region's structure broke (unclosed code fence, dangling marker, heading
  level change). Closes a real correctness hole: today the tool will
  happily corrupt a file as long as bytes *outside* the region don't move.
  Safer correctness bet.
- **MCP server wrapper** — expose `list_regions` / `get_region` /
  `replace_region` over [MCP](https://modelcontextprotocol.io). Turns the
  "agent-friendly" claim from aspirational into real — any MCP-aware agent
  gets region-scoped markdown edits without shelling out to a CLI and
  parsing text. Bigger positioning bet.

## Ideas (post-v0.3)

Not ranked. Each is a real bet someone could pull off the shelf.

- **Integrate Anthropic's text-editor tool.** The text editor tool gives
  the model a native `str_replace` primitive. surgical-md could either be
  the region-aware splice backend behind it, or wrap it so agents that
  prefer the native tool still get markdown-region semantics.
- **Ship to PyPI.** Currently install-from-git only by design, pending a
  security review. After that: a proper PyPI release, signed builds,
  changelog.
- **Rust rewrite.** Single static binary, no Python runtime required,
  faster startup. Worth doing once the addressing model is frozen and the
  test suite is effectively the spec.
- **VS Code extension.** Surface regions as document symbols (LSP-style),
  let users splice from inside the editor, integrate with whichever LLM
  tooling is active.
- **MDX / YAML frontmatter support.** Either extend the existing region
  kinds or formalize that "surgical-md is for markdown-ish text" so the
  scope question stays answered.
- **Multi-file batch mode.** "Edit `agent-rules` in every `CLAUDE.md`
  across the monorepo, atomically, with one rollback." A real cross-file
  primitive — not a shell loop.
- **Durable index / JSON sidecar.** Pre-computed map of each file's
  regions and their semantic purposes, regenerated on file change. Cheap
  per-edit lookups for agents that need to decide *which* region to edit.
- **`--patch` / diff-aware editing.** Apply a unified diff scoped to a
  single region; refuse if the diff lands outside.
- **Undo log / backup on write.** A `.surgical-md/` audit trail of every
  splice, with revert.

## Known critiques to keep honest

- The token-economics pitch is half-true in 2026 — prompt caching makes
  "send the whole file once, edit N times" cheap, so the savings come less
  from smaller input and more from smaller, focused output the model can't
  drift outside. Lead with bounded blast radius + deterministic splice.
- "Smallest containing region" regex behavior is clever but surprising — a
  match on a phrase can return the entire enclosing `##` section. Consider
  a preview mode that shows what was picked before splicing.
- Line-ending normalization (Windows, `core.autocrlf`, BOM, editor
  "strip-trailing-whitespace", macOS Unicode normalization) can defeat
  `--expect-hash` on content that "didn't change." Atomic-write story has
  honest edges; document them when they bite.
