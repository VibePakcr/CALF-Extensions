# H3 GitLab pinned ref, tree and raw blob reader

[한국어](REPOSITORY_HOSTED_H3_KR.md) · [Hosted plan](REPOSITORY_HOSTED_PLAN.md) · [Qualification](verification/repository-hosted-h3-20261107.json)

2026-11-07 · GitLabSource implemented · macOS Git-backed fixtures and scoped public raw reads verified

H3 adds `providers/gitlab.py` as a common SourceReader implementation. A manually registered, identity-verified GitLab.com project resolves a typed ref to a full SHA-1 commit, reads that commit's paginated inventory and collects bounded raw blob bytes. Existing GitHubSource, Local Git, HTTP policy, analyzer, CLI, UI assets, FFmpeg and CALF records remain unchanged.

## Reader interface

Register the chosen project and explicitly run H1 `sources check SOURCE_ID --data-dir APP_DATA`, then load the verified registration. GitLab subgroups are supported by H1 registration; collection uses the bound numeric project ID.

```python
from calf_extensions.repository.registrations import Registry
from calf_extensions.repository.providers.gitlab import GitLabSource
from calf_extensions.repository.capture import Store
from calf_extensions.repository.analyze import analyze_snapshot

source = GitLabSource(Registry(APP_DATA).get(SOURCE_ID))
try:
    revision = source.pin("branch", "main")  # Or ("tag", "v1") / ("commit", FULL_SHA1)
    snapshot = source.snapshot(revision)
    graph = analyze_snapshot(snapshot, SETTINGS)
    capture_id = Store(APP_DATA, create=True).save_snapshot(snapshot)
    coverage = source.report  # Retain a serialized copy with the snapshot when needed.
finally:
    source.close()
```

`SETTINGS` is an optional existing feature/glossary dictionary. App data belongs outside source repositories and existing CALF records. `snapshot(revision, path_ids={...})` supports explicit source selection using `model.path_record(raw_path_bytes)["id"]`. Unselected files remain NOT_FETCHED. `cancel=threading.Event()` and `budget=Budget(...)` constructor options share operation limits across pinning, pages and blobs. The synchronous reader returns an immutable Snapshot; it does not save or activate one automatically. H1 identity-job routes remain identity-only. Hosted source-selection UI, `open/scan --source`, provider editor/permalinks and v2 offline export remain H4.

## Ref, inventory and byte semantics

- Distinguish branch/tag/full-commit requests, validate the exact returned name, and use the tag endpoint's dereferenced `commit.id` for annotated tags. Subsequent commit/tree reads use the full pinned commit; raw blob reads use the inventory's SHA. Invalid refs fail before network access. Verify numeric project identity and canonical namespace; renamed registrations require an explicit H1 check/reload.
- Keep `Revision.tree_oid=None`. The supported GitLab commit API does not expose the root tree OID. `source.report.tree_oid_reason` records `NOT_EXPOSED_BY_GITLAB_COMMIT_API`; retain the report if that reason must survive reopening. The inventory digest is a separate normalized SHA256, not a Git tree identity. Commit-to-inventory binding and completeness are API assertions, not independent raw-commit/root-tree proof.
- Request recursive tree pages with `ref=FULL_COMMIT`, `pagination=keyset` and `per_page=100`. H1 validates next links against origin, numeric project, endpoint, pinned ref and parameters; pages inherit request/auth/cancellation budgets. Duplicate paths/pages, cursor loops, malformed links, missing parents in a complete inventory and conflicting modes fail explicitly. No total-count header is required or treated as completeness proof.
- A final short page with no next link completes the API inventory. A full 100-item page without next metadata is conservatively `PAGINATION_END_UNKNOWN` with incomplete inventory, even if it could be the actual final page. Do not infer absence from incomplete inventory. Valid empty trees and inaccessible/missing 404 responses remain distinct.
- Read **only `/repository/blobs/SHA/raw`** for file bytes. JSON file/blob responses can transcode non-UTF8 content; H3 never uses them as originals. Check the raw byte count, Git blob SHA-1 and SHA256. Keep empty, BOM, CRLF, binary, non-UTF8, unsupported text and NOT_FETCHED distinct. A JSON MIME type does not cause raw file bytes to be decoded as JSON.
- Preserve UTF-8 path bytes without normalization, including distinct Unicode spellings and control characters that Git permits. Reject invalid/traversal/ambiguous replacement paths, incorrect names and mode/type mismatches. Keep symlink/submodule entries without following targets, and LFS pointer bytes without LFS downloads.
- Keep H1 fixed HTTPS origins, credential references, scoped cache, rate handling and owned worker cancellation. Default budget remains 300 requests/120 seconds. Additional bounds are 32 MiB aggregate metadata, 50,000 inventory records, 128 path levels, 1 MiB/raw file and 64 MiB total materialized bytes. Repeated blobs are fetched once but count per materialized path.
- Surface budget/rate/size gaps in inventory/content coverage and report reasons. Corruption/access/contract failures fail; cancellation/deadline failures return no new usable snapshot. The caller inspects coverage before retention or activation. No active map, prior capture, authority or CALF receipt is replaced by this reader.

## Observed qualification

The final repository suite passed **101 checks: 81 existing + 20 H3**. Three FFmpeg contract checks passed too. Git-backed fixtures cover annotated tag/branch collisions, moving refs, exact Unicode/raw bytes/modes, a 1,005-entry paginated tree, next-link scope/loops/overlap, missing pagination metadata, empty versus 404, source/metadata bounds, corruption, cancellation, retained-v2 roundtrip and complete normalized Local/GitLab map plus direct Diff equality. Actual owned HTTP subprocess checks preserved non-UTF8 raw bytes even with JSON MIME type, and cancelled a stalled raw read without publishing a Snapshot.

Actual anonymous reads used the existing public [GitLab CALF-Extensions mirror](https://gitlab.com/vibepackr-group/CALF-Extensions), project `88597295`, pinned commit `814b6c27fe9ac68ad3f9bb6db7fe2e8ba95f65d1`. Inventory contained **32 files**. **10 selected Python files / 53,473 bytes** matched independently retained local Git blobs at the same paths; their selected code subgraphs matched. The full remote map had 163 nodes/508 edges. The successful attempt used **20 requests / 17.031 seconds** and reloaded retained v2 unchanged. Two inventory passes each returned a single page; this is not a live multi-page fixture qualification.

The mirror's current commit was not retained in the local repository, and the local H2 baseline commit could not be read through the mirror API. Those first two attempts remain recorded. The successful live check compares selected retained blobs/subgraphs across the two pinned commits; **full same-commit Local/GitLab inventory/map equality remains NOT_RUN**. Full equivalence is demonstrated by the independent synthetic Git fixture, not claimed from this live mirror.

All **32 existing repository source files**, including GitHubSource and the shared analyzer/UI/HTTP modules, retained their H3-start hashes. Nine historical H0–H2 documents/reports and unrelated README/package edits matched. The initial preservation audit matched all 607 files; the final audit matched **606/607**, with one external application runtime configuration change observed. This task neither modified nor restored that configuration; both observations are retained. No native CALF record writes, provider writes, clone/fetch/push, owner credential use or commit/push occurred. Owned workers/threads stopped. The unchanged H2 actual Chrome live/offline evidence is reused after source/asset hash verification; no new browser or hosted UI qualification is claimed.

Private GitLab access, live tag/Unicode/multi-page edge cases, Self-Managed, SHA-256 Git objects, H3 on Windows/Linux, hosted UI/export, package installation, performance/peak-memory and physical devices remain NOT_RUN. All full HG01–HG32 states remain NOT_RUN; H3 adds scoped reader progress only. Next is H4's shared source-selection/map/code/Diff flow.

Contracts: [repository tree and raw blobs](https://docs.gitlab.com/api/repositories/), [branches](https://docs.gitlab.com/api/branches/), [tags](https://docs.gitlab.com/api/tags/), [commits](https://docs.gitlab.com/api/commits/), [pagination](https://docs.gitlab.com/api/rest/#pagination).

END
