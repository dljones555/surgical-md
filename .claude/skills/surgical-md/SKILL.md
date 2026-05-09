---
name: surgical-md
description: Use this skill to surgically edit a specific named region of a Markdown file — by id, class, `<!-- SECTION: name -->` markers, heading text, or regex — instead of rewriting the entire file. Trigger whenever the user wants to modify just one section/heading/block of a `.md` file (CLAUDE.md, agent rules, prompt libraries, runbooks, RFCs, READMEs, design docs), references a named region like "the agent rules section" or "the roadmap section", or asks to tighten/update/replace/edit a specific part of a markdown document. This avoids the token cost and unintended drift of whole-file LLM rewrites by sending only the named region to the model and splicing the result back byte-exactly. Use this even when the user doesn't explicitly say "surgical" — strong keyword cues include "just the X section", "only the heading on Y", "tighten the rules", "update the roadmap", "replace the part about Y", "fix the wording in <heading>", or any request to change a portion of a markdown file rather than the whole thing.
---

# surgical-md

A region-scoped Markdown editor. The model sees only the section being
edited; bytes outside it are guaranteed unchanged.

## Why this skill exists

Whole-file LLM rewrites are expensive and lossy. Sending a 2,000-line
`CLAUDE.md` to tighten its "agent rules" section costs ~10× the tokens it
should and produces drift in unrelated paragraphs. With this skill the model
sees only the named region — cheaper, faster, focused outputs, and
provably-bounded blast radius.

## When to reach for this

- Editing a specific heading, section, or block of a markdown file rather
  than the whole document
- The user names a region: "the rules section", "the API heading", "the
  TODO list", "the part where I describe X"
- The file is meant to be edited repeatedly (CLAUDE.md, agent rules, prompt
  templates, runbooks, structured RFCs, design docs)
- You want atomic writes that won't clobber a concurrent edit

Skip this skill for: small files where loading everything is cheap, ad-hoc
typo fixes, or files with no addressable structure (no headings, no markers,
nothing to anchor to). For those, the standard Read + Edit flow is fine.

## Verify install before use

```bash
surgical-md --version
```

If the command isn't found:

```bash
uv tool install git+https://github.com/dljones555/surgical-md
# or, inside a clone of the repo:
uv sync && uv run surgical-md --version
```

## Core workflow

The whole loop is three commands. Always include the hash check for atomic
writes — if anything else touched the file between read and write, the
splice is refused rather than silently clobbering.

```bash
HASH=$(surgical-md hash FILE)
surgical-md show FILE --section rules \
  | <your transform — LLM call, sed, awk, anything> \
  | surgical-md replace FILE --section rules -i --expect-hash "$HASH"
```

`-i` writes back in place. Without it, output goes to stdout. Use `-n`
(`--dry-run`) to preview the splice as a unified diff without writing.

In PowerShell (no `<<<` here-string operator):

```powershell
$hash = surgical-md hash FILE
surgical-md show FILE --section rules `
  | <transform> `
  | surgical-md replace FILE --section rules -i --expect-hash $hash
```

## Selectors — pick the right one

| Selector | Use when | Notes |
| --- | --- | --- |
| `--section NAME` | File has `<!-- SECTION: NAME --> ... <!-- END-SECTION: NAME -->` markers | Most reliable; named explicitly by the author |
| `--id NAME` | Heading has explicit `{#name}`, OR the heading-text auto-slug matches | `## My Heading` auto-IDs to `my-heading` |
| `--class NAME` | Heading or fenced div tagged with `.name` | Returns *all* matching regions |
| `--regex PATTERN` | You only remember a phrase from the section | Returns the smallest enclosing region per match |

`replace` refuses ambiguous selectors. If a `--class` or `--regex` matched
more than one region, refine — don't try to disambiguate by trial and error.

## Safety patterns

**Preview before you commit.** When in doubt, run `replace ... -n` first to
see the unified diff:

```bash
echo "$NEW" | surgical-md replace FILE --section rules -n
```

**Atomic writes via `--expect-hash`.** Capture the hash before reading,
re-supply it on write. If something else changed the file in between, the
write fails with exit code 2.

**Exit codes are meaningful:**
- `0` — success
- `1` — no match (selector found nothing). Do not retry without changing
  the selector — confirm the region exists with `surgical-md list FILE`
- `2` — cannot proceed (ambiguous selector, hash mismatch, missing
  selector). Inspect stderr for the reason

**Errors go to stderr, data to stdout.** Pipelines stay clean.

## Decorating an undecorated file

If the user wants surgical edits on a file with no anchors yet, add them
first. Two equally good options — pick the one that fits the file:

**HTML comment markers** (best for prose, agent rules, anything where you
don't want a visible heading or where the natural unit isn't a heading
section):

```markdown
<!-- SECTION: agent-rules -->
- be terse
- show diffs
<!-- END-SECTION: agent-rules -->
```

**Pandoc heading attributes** (best for already-structured documents):

```markdown
## My Section {#my-id .draft}
```

Auto-IDs cover the common case — `## Roadmap` is already addressable as
`--id roadmap`. Add explicit `{#id}` only when the auto-slug is wrong or
ambiguous.

## Worked examples

### Example 1: tighten the agent-rules section in CLAUDE.md

User says: *"tighten the agent rules section in CLAUDE.md"*

```bash
HASH=$(surgical-md hash CLAUDE.md)

# Read just that section into the conversation:
surgical-md show CLAUDE.md --section agent-rules

# (Model produces tighter version as $NEW)

# Splice back, atomically:
echo "$NEW" | surgical-md replace CLAUDE.md --section agent-rules \
  -i --expect-hash "$HASH"
```

If the file has no `<!-- SECTION: agent-rules -->` markers yet, list what's
there: `surgical-md list CLAUDE.md`. Pick the matching heading section and
use `--id <slug>` instead.

### Example 2: rewrite the "## Roadmap" heading section

User says: *"rewrite the roadmap heading in PLAN.md to focus on Q2"*

`## Roadmap` auto-IDs to `roadmap` — no decoration needed.

```bash
HASH=$(surgical-md hash PLAN.md)
surgical-md show PLAN.md --id roadmap | <transform> | \
  surgical-md replace PLAN.md --id roadmap -i --expect-hash "$HASH"
```

### Example 3: find a section you only remember by phrase

User says: *"update the part where I talk about flaky tests"*

Use regex to locate the smallest containing region:

```bash
surgical-md grep NOTES.md 'flaky tests'
# → NOTES.md:42: heading_section #testing-strategy h2

# Now operate on it:
HASH=$(surgical-md hash NOTES.md)
surgical-md show NOTES.md --id testing-strategy \
  | <transform> \
  | surgical-md replace NOTES.md --id testing-strategy -i --expect-hash "$HASH"
```

## Pitfalls and limits

- **Heading-section extent.** A heading section runs from the heading line
  to the next heading of *equal or higher* level. `## Notes` includes its
  `### Subnotes` children but ends at the next `##` or `#`.
- **Ambiguity is loud, not silent.** Two `## Roadmap` headings → same
  auto-id → `replace` exits 2. Disambiguate with `--regex` or by adding an
  explicit `{#id}` to one of them.
- **Setext headings** (`===` / `---` underlines) are not parsed. Convert to
  ATX (`#`) or use `<!-- SECTION -->` markers.
- **Auto-IDs are ASCII-only.** Non-ASCII letters are dropped from the slug.
  Use an explicit `{#id}` if needed.
- **Code-fence masking.** Attribute-shaped text inside fenced code blocks
  is ignored — useful, but it means a `## Heading` inside a fenced code
  block won't be addressable.

## Quick reference card

```
LIST       surgical-md list FILE
SHOW       surgical-md show FILE <selector>
REPLACE    surgical-md replace FILE <selector> [-f PATH] [-i] [-n]
                                    [--expect-hash SHA256]
GREP       surgical-md grep FILE PATTERN
HASH       surgical-md hash FILE
VERSION    surgical-md --version

selectors  --id NAME | --class NAME | --section NAME | --regex PATTERN
flags      -i / --in-place    write back to FILE
           -n / --dry-run     unified diff, no write
           -f / --file PATH   new content from file (default: stdin)
exit codes 0 success | 1 no match | 2 cannot proceed
```
