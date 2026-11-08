# History queries: platform and fresh-session qualification

[한국어](REPOSITORY_HISTORY_QUALIFICATION_KR.md) · [Commands](REPOSITORY_HISTORY.md) · [Structured evidence](../REPOSITORY-HISTORY-QUALIFICATION-20261108.json)

The unchanged **Repository Pack 0.1.1-preview.4** ZIP received additional qualification on 2026-11-08. Its SHA-256 is `a2315cbbd9fc76994d6ee11c04b14f3e832d71aec9bd63d2f0dc4e63456f75fe`. No core or runtime update is required to use these results. Earlier packages and their original manuals remain intact.

## Windows and Linux

Windows x64 / Python 3.12.10 and Debian x64 / Python 3.13.5 each passed all 21 new history-boundary tests, with zero skips. Both used their released Harness 1.8.8 executable. Each test installation qualified the previous and current packs, updated, rolled back and selected the current version again without changing retained locks.

On each system, 76 newly generated native records were compared with their original references. CJK output, an older rule outside the 20 recent notes, exact-record reads, chain-damage refusal, stale-index refusal and rebuilding into a new directory passed. A real native check passed, then returned `UNKNOWN` after its checked file changed. Existing files remained identical: 744 on Windows and 878 on Linux. These tests used new local stores and synthetic projects, without installing system tools or replacing the owner's active application.

## Continuing in a fresh session

New Codex app-server, Antigravity ACP and Claude Code sessions received no prior conversation or answer values. The supplied workspace instructions identified a local query route. Each recovered the older map constraints, cited the exact original sequence/ID/hash and reported current `UNKNOWN`; other module notes were not read by that route.

The four operations were: recent module notes → older-rule search → exact original record → current native status. Each returned 8,345 structured response bytes for a 125,216-byte synthetic journal. Host instructions, transport wrapping and diagnostics are excluded. Module/search queries read metadata without the journal body; the exact record read 732 source bytes. Current status deliberately rehashed the whole source. This measures returned data, not LLM tokens, total host I/O or a speed multiplier.

Codex reported loading the workspace `AGENTS.md` automatically. Antigravity used the configured workspace query route; its instruction-source metadata was not separately exposed. Claude's ordinary Bash trial recovered the right answer but failed the original strict test because it also looked for its workspace-specific native memory index and read the local bootstrap. That failure remains recorded. A different fresh Claude session then passed using only four ephemeral read-only MCP tools, with Bash and directory tools unavailable. It connected before the model prompt and exited cleanly.

This MCP adapter is a **task-scoped test connection**, not a new general Repository MCP server shipped inside the ZIP. The host tests are native programmatic sessions; they do not qualify a new GUI session, ordinary Claude chat, Cowork or a cloud session.

## Use the workflow in your own project

Build an index with your explicit module mapping as described in [Local history queries](REPOSITORY_HISTORY.md). Add a short locator to the instruction file you already use: `AGENTS.md` for Codex, `GEMINI.md` for Antigravity or `CLAUDE.md` for Claude Code. Preserve the existing instructions. A locator should name the selected Python/Repository installation, index and reviewed native executable, then explain:

1. Select the module named by the task and read `history module --module MODULE` first.
2. Use `history search` when the recent notes omit a needed constraint.
3. Read the selected sequence with `history record` and cite its retained identity.
4. Use `history status` for a current native verdict. Never promote historical success from Markdown.

The existing guide gives full commands; use `python -X utf8 -B` on Windows. Paths and module mappings remain explicit. This release does not automatically discover every project, infer all module boundaries or inject old records into unrelated sessions. No watcher, database or background agent is added.

## Preservation scope

The local audit retained 938 original history prefixes and the existing contracts/execution settings. Of 818 initially protected files, 817 were byte-identical; one concurrent UI artifact-summary/timestamp update was reviewed separately. No settings or baseline were restored. An existing CLI test-profile cache was omitted from the initial capture; its runtime backup comparison showed only `oauthAccount.profileFetchedAt` changing. The prior cleanup-marker bytes were unavailable, so whole-profile byte preservation is not claimed. Exact scope, retained first failures and measurement limits are recorded in the structured evidence.
