# H0 common source contracts: implementation and qualification

[한국어](REPOSITORY_HOSTED_H0_KR.md) · [Hosted plan](REPOSITORY_HOSTED_PLAN.md) · [Qualification](verification/repository-hosted-h0-20261107.json)

2026-11-07 · H0 implemented · macOS contracts/Local UI verified · GitHub/GitLab transports remain unimplemented

`providers/base.py` adds frozen RepositoryIdentity, Revision, Entry, Content, Snapshot, Capabilities and the SourceReader protocol. LocalSource in `providers/local.py` wraps the existing GitReader, v1 collection and exact source reads. `analyze_snapshot` consumes common content without filesystem paths or Git commands. Existing `analyze(reader,store,capture,settings)` and `compare.source` entry points remain compatibility wrappers.

## Identities and persistence

- Distinguish pinned commits from local working state. Working content is not presented as HEAD commit content.
- Resolve branch/tag names explicitly and dereference annotated tags. Once pinned, read commit/tree/blob identities even when the branch moves, without checkout.
- Distinguish READY zero bytes from ABSENT, NOT_FETCHED, UNAVAILABLE and LIMIT_EXCEEDED. Partial inventory cannot prove deletion.
- New v2 captures are create-only `captures-v2/<snapshot-id>.json` files. Never rewrite/move v1 captures. A v1 snapshot with retained bytes remains readable without its original repository.
- `snapshot_id` preserves existing v1 capture IDs. Separate `input_id` binds materialized bytes and availability. Both IDs are identical for v2.
- `navigation_id` binds input ID, mapping digest, analyzer version and graph schema. ComparisonContext also binds both input IDs, keeping incomplete cache coverage distinct from complete inputs.
- Snapshot/Content data are immutable; a cancel event is separate operational state excluded from identity. Retain 1 MiB/file, 64 MiB aggregate and metadata bounds.

## Developer interface

These Python interfaces are implemented. They need no credentials, HTTP or automatic repository registration.

```python
from calf_extensions.repository.providers.local import LocalSource
from calf_extensions.repository.providers.base import ComparisonContext
from calf_extensions.repository.analyze import analyze_snapshot
from calf_extensions.repository.compare import compare_pair

source = LocalSource(project_directory, app_data_directory)
revision = source.pin("branch", "main")
snapshot = source.snapshot(revision)
snapshot_id = source.store.save_snapshot(snapshot)
restored = source.store.load_snapshot(snapshot_id)
graph = analyze_snapshot(restored)
# After obtaining another Snapshot from the same repository:
# result = compare_pair(ComparisonContext(restored, other), path_id)
```

Keep existing `python -m calf_extensions.repository.cli open --repo ... --data-dir ...` and v1 code/Diff/export behavior. v2 capture retention/analysis contracts exist, but v2 navigation CLI export belongs to H4 and is explicitly refused in H0. `sources add` and `open --source` are not implemented yet.

## Observed qualification

The complete 34-check suite passed: 22 existing checks plus 12 H0 checks. The H0 12 were repeated after the final comparison-input identity refinement. Three FFmpeg contract checks and v2 JSON Schema/actual serialized fixture checks passed too.

Actual macOS Chrome covered the map, below-map code/Diff, call line, bookmarks, EN/KO, 1440/390/320 widths and emulated pinch. v1 offline viewing passed with originals hidden and HTTP blocked. Test server/browser processes stopped. Physical phones and actual external editor launching remain unqualified.

GitHub/GitLab-shaped memory snapshots produced equivalent normalized file/symbol/document/call maps. Socket and subprocess calls were forbidden during this analysis, proving it does not depend on transport or project execution. This is not live GitHub/GitLab support qualification. Windows/Linux reruns, packaging and performance for H0 changes remain unqualified.

All 15 FFmpeg/license/release files, 27 historical v1 files and 565 files in the existing preservation set retained their H0-start hashes. Three historical v1 snapshots were actually loaded without changing files. Original CALF records were not modified.

Next is H1: manual registration, credential references, bounded HTTP and collection/cancellation jobs. Full hosted acceptance remains NOT_RUN; H0 adds contract-fixture evidence only.

