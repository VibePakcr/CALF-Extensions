# Local history queries

[한국어](REPOSITORY_HISTORY_KR.md) · [Repository pack](REPOSITORY_PACK.md)

This source preview reads an explicitly selected CALF `history.html`. It creates a small index and module notes without changing the original journal, hash chain, contracts or completion rules. The generated files are disposable views; CALF never imports them as evidence.

Indexing and reading use Python 3.10+ and its standard library. No Git, SDK, model, network or background service is involved. Native chain confirmation and current verdict queries additionally need an explicitly selected CALF executable. Harness 1.8.8 integration is qualified on macOS ARM64, Windows x64 and Debian x64. Fresh local Codex, Antigravity and Claude Code context tests are documented in the [follow-up qualification](REPOSITORY_HISTORY_QUALIFICATION.md). Other versions and environments need separate qualification.

## Define the modules

Save a separate UTF-8 JSON file:

```json
{
  "schema": "calf.repository.history-modules.v1",
  "modules": [
    {"id": "map", "label": "Map viewer", "paths": ["src/map"], "dependsOn": ["api"]},
    {"id": "api", "label": "API", "paths": ["src/api"]},
    {"id": "auth", "label": "Authentication", "paths": ["src/auth"]}
  ]
}
```

IDs use lowercase ASCII letters, digits, underscores and hyphens; labels support Unicode. Paths are safe project-relative prefixes. A task whose scope overlaps a module belongs to that view. Overlap works in both directions: scope `src` can affect `src/map` and `src/api`. Shared tasks appear in each matching module. Declared scope is not proof of the files actually changed.

For observed tasks without file scope, use `"tasks": ["exact-task-id"]`. Paths and task IDs can be combined. Unmapped or unresolved references remain in `unassigned`. Dependencies are explicit, not inferred from prose. `--related` adds up to four direct neighbors and reports any omitted ones.

## Build and read

Run from the extracted Repository pack or CALF Extensions source root. Use physical absolute paths and an existing output parent. The output must be a **new directory outside the history's workspace**.

```text
python -B -m calf_extensions.repository.cli history build --history /work/project/history.html --modules /work/config/modules.json --output /work/data/history-view-001
python -B -m calf_extensions.repository.cli history modules --index /work/data/history-view-001
python -B -m calf_extensions.repository.cli history module --index /work/data/history-view-001 --module map
python -B -m calf_extensions.repository.cli history module --index /work/data/history-view-001 --module map --related --json
python -B -m calf_extensions.repository.cli history search --index /work/data/history-view-001 --module map --kind DECISION
python -B -m calf_extensions.repository.cli history search --index /work/data/history-view-001 --module map --query architecture --before 120 --limit 10
python -B -m calf_extensions.repository.cli history record --index /work/data/history-view-001 --seq 42
```

The output contains `INDEX.json`, metadata pages under `pages/`, and `sub_map.md`, `sub_api.md`, `sub_auth.md` and `sub_unassigned.md`. Notes show at most 20 recent records, their original sequence/ID/hash, historical outcomes and the number omitted. Exact older entries remain available by sequence. Recorded text is untrusted reference material, not instructions from the reader.

A module query reads the manifest and selected Markdown only. It does not load unrelated notes or journal contents. An exact-record query reads one metadata page and seeks to the original byte range, checking its retained raw digest and identity. Modified notes or metadata pages are refused.

`search` finds older module records in the small metadata pages, including entries outside the recent notes. It searches IDs, kinds and the first 160 body characters, not full payloads. Results are newest first and contain at most 20 references. Continue with the returned `nextBefore`; a `PARTIAL` result is not a complete-history claim. Each call scans up to 8 MiB of metadata, plus at most one bounded page, without reading the journal body. Read a result's `seq` for its exact full record.

Default freshness compares the source's identity, size, modification time and change time (`STAT_MATCH`). Add `--verify-source` to a read command for a full SHA-256 comparison (`SHA256_MATCH`), which necessarily reads the whole source. An append makes the index stale; rebuild into a new directory. No watcher, automatic refresh or cache eviction is installed.

## Integrity and current completion

The basic build checks envelope continuity only. It does not reimplement CALF's native schema/hash algorithm. To require native confirmation of the indexed head, add the reviewed executable:

```text
python -B -m calf_extensions.repository.cli history build --history /work/project/history.html --modules /work/config/modules.json --output /work/data/history-view-002 --calf /work/tools/calf
python -B -m calf_extensions.repository.cli history status --index /work/data/history-view-002 --task exact-task-id --calf /work/tools/calf --verify-source
```

These use the existing read-only `calf status WORKSPACE TASK` interface. Confirmation requires a typed response for that task, an unchanged source SHA-256 around the call, and a native `head` matching that whole-file digest. In the qualified core, this differs from the journal's last envelope hash; both identities are retained separately. Its task outcome may still be `UNKNOWN` or `VIOLATED`. An explicit status query also rehashes the source before returning the current verdict. Notes always mark current completion as `NOT EVALUATED`; stored `SATISFIED` text stays historical. Current file versions, execution environment and evidence rules remain in force. A different environment may return `UNKNOWN` after an earlier host run passed. No test, worker, repair, retry or adoption is launched.

The source is read in 32 KiB chunks. Bounds are 1 MiB per record, 256 MiB per source, 100,000 records, 4,096 tasks and 64 configured modules. Interrupted/refused builds can leave a new partial directory; it is unreadable without the final `INDEX.json`. Existing outputs are never overwritten. A source change during building prevents completion. Human-only legacy HTML without the supported inert record blocks is refused rather than converted.

Views may contain private paths and excerpts. They are not automatically redacted for publication. Creating or reading one does not upload it or send it to an AI. Hash checks detect changes at inspection boundaries; this is not authentication or isolation from a malicious process controlling the same files.

## Qualification

```text
python -B -m unittest calf_extensions.repository.tests.test_history_index -v
```

These tests cover seek accuracy, selective reads, preservation, CJK, shared scope, explicit mapping, stale/tampered inputs and limits. They are separate from the pack manager's existing Git `inspect` qualification. Actual native integration and retained-work comparisons are checked separately; a Git qualification result does not certify this feature.

Structured responses expose Python-side `sourceBytesRead` and `indexBytesRead`; native I/O is explicitly unmeasured. Compare response bytes, query time and reference coverage against the same source. No fixed token reduction or speed multiplier is promised. This addition does not include a Workbench panel, MCP server, incremental append indexer or new core release.
