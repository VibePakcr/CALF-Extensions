# H2 GitHub pinned ref, tree and blob reader

[한국어](REPOSITORY_HOSTED_H2_KR.md) · [Hosted plan](REPOSITORY_HOSTED_PLAN.md) · [Qualification](verification/repository-hosted-h2-20261107.json)

2026-11-07 · GitHubSource implemented · anonymous public GitHub reader qualified on macOS

H2 implements the common SourceReader boundary for an explicitly registered, identity-verified GitHub.com repository. It pins a branch, tag or full 40-character commit, collects a verified inventory and bounded original bytes, and returns an immutable H0 Snapshot. It adds one SHA-addressed annotated-tag read template to H1 HTTP policy. The reader does not register accounts, execute project code or publish an active map.

## Use the Python reader

First register the chosen repository and explicitly run H1 `sources check SOURCE_ID --data-dir APP_DATA`. Load the verified registration from that same app-data directory. The reader requires identity verification; a changed canonical name returns `REGISTRATION_STALE`, so explicitly check and reload the registration after a rename.

```python
from calf_extensions.repository.registrations import Registry
from calf_extensions.repository.providers.github import GitHubSource
from calf_extensions.repository.capture import Store
from calf_extensions.repository.analyze import analyze_snapshot

registration = Registry(APP_DATA).get(SOURCE_ID)
source = GitHubSource(registration)
try:
    revision = source.pin("branch", "main")  # Or ("tag", "v1") / ("commit", FULL_SHA1)
    snapshot = source.snapshot(revision)
    graph = analyze_snapshot(snapshot, SETTINGS)
    # Deliberate retention; use app data outside source repositories/CALF records.
    capture_id = Store(APP_DATA, create=True).save_snapshot(snapshot)
    coverage = source.report
finally:
    source.close()
```

`SETTINGS` is the existing optional feature/glossary mapping dictionary. For bounded selective collection, pass `path_ids={path_record(path_bytes)["id"], ...}` to `snapshot`; import `path_record` from `repository.model`. Omitted files remain NOT_FETCHED, even when inventory is complete. A complete inventory does not mean all source was fetched or analyzed. Constructor options `cancel=threading.Event()` and `budget=Budget(...)` share cancellation/request limits across pinning and collection. This is a synchronous foreground reader; H1 identity-job APIs remain unchanged. Hosted `open/scan --source`, source-selection UI, provider editor/permalinks and v2 offline export remain H4. Existing Local Git commands and FFmpeg workflows keep their interfaces.

## Exactness and failure behavior

- Keep branch and tag namespaces distinct; validate the exact returned ref. Resolve annotated tags by object SHA with loop/type/depth checks, then read the full pinned commit/tree. SHA-256 Git object format and implicit HEAD/default-branch selection are not offered by this GitHub reader.
- Validate the registered numeric identity and canonical name. Reject commit/tree/repository mismatches. GitHub's commit-to-tree binding is provider-reported; H2 does not claim independent raw-commit or signature verification.
- Try the recursive Git Trees endpoint. If truncated, discard that incomplete listing and traverse SHA-pinned nonrecursive subtrees. Reconstruct complete Git tree bytes and verify their SHA-1, including raw UTF-8 names, modes and Git ordering. Never use Contents directory listings as a complete inventory. A still-truncated subtree or exhausted inventory budget cannot prove absence; expose `inventory_complete=False` and report reasons.
- Fetch only selected regular blobs. Strictly decode Base64 and verify reported size, inventory size, blob SHA-1 and raw-byte SHA256. Zero bytes remain a real READY empty file; corrupt, missing or unfetched bytes never become empty text. Binary/BOM/CRLF/non-UTF8 content retains original bytes and explicit text availability.
- Preserve symlink/submodule entries without reading targets; keep LFS pointer bytes without downloading LFS objects. Unsupported/lossy API paths, including ambiguous replacement characters, fail explicitly. Exact representable Unicode, spaces, plus/percent/hash, tabs and newlines retain byte identities without normalization.
- Retain H1 destination/authentication/cache/retry controls and the shared default 300-request/120-second budget. Add 32 MiB aggregate metadata, 50,000 inventory items, 128 subtree levels, 16 tag-dereference steps, 1 MiB/file and 64 MiB materialized source limits. Count materialized bytes per path even when blob reads are deduplicated.
- Request/rate/size limits can produce explicit partial inventory/content, with reasons in `source.report`; malformed or mismatched data fail. Cancellation/deadline failures return no new usable snapshot. The caller must inspect coverage before retention/activation. The reader never changes an existing active capture or existing v1 files.

The common analyzer also needed a compatibility repair found by the live repository check: grouped imports emitted identical edges, while repeated calls on one line lacked distinct locations. `python-ast-v3` deduplicates identical relationships and adds AST start/end columns (zero-based UTF-8 byte offsets, exclusive end) to preserve distinct call sites. Its analyzer/navigation identity changes accordingly; historical captures/navigation are not rewritten.

## Observed qualification

The final repository suite passed **81 checks: 62 previous + 19 H2**, and three FFmpeg contract checks passed. H2 uses independently generated real Git objects for ref movement/collisions, annotated tags, complete/truncated trees, a 1,005-file directory, exact paths/bytes/modes, corruption, size/budget gaps, cancellation, retained-v2 roundtrip and normalized Local/GitHub graph plus direct Diff checks. An owned HTTP subprocess exercised the annotated-tag endpoint too.

Actual anonymous GitHub API reads used public [VibePakcr/CALF-Extensions](https://github.com/VibePakcr/CALF-Extensions) at commit `66bdf4a6e8d19ec87b4a10b9e541f1fe3870dc02`, API version `2026-03-10`: all **56 inventory entries** matched independent local Git objects; **13 selected files / 82,756 bytes** matched exactly. The normalized graph matched (225 nodes / 516 edges), and retained v2 reloaded unchanged. The successful attempt used **19 requests / 9.688 seconds**. The earlier live graph failure and its local diagnosis are retained separately.

Fresh actual macOS Chrome Local live/offline regression passed map/code/Diff, call lines, bookmarks, EN/KO, emulated pinch and 1440/390/320 widths with no runtime errors. Original fixture sources were hidden for offline viewing. This is Local UI regression evidence; the hosted-source UI has not been implemented. Servers, sockets and owned test browsers stopped.

FFmpeg/license/release files, historical v1 artifacts, existing CALF material, the six H0/H1 documents/reports and unrelated README/package working edits retained their baseline hashes. Of the broader 607-file preservation set, **606 were unchanged**; one external application runtime configuration changed during the task. Its contents were not edited/restored by this task. A pre-existing process-limit fixture once encountered OS `killpg` EPERM; its unchanged focused rerun and subsequent full suite passed. The first failure stays in the qualification record; its intermittent OS cause is not claimed resolved by H2.

GitLab collection (H3), actual private access, live annotated-tag/truncation/path-edge cases, Windows/Linux H2, hosted map UI/export (H4), package installation, performance/peak-memory qualification and physical devices remain NOT_RUN. Full HG01–HG32 acceptance remains NOT_RUN; scoped GitHub public-reader progress is recorded separately. No provider writes, clone/fetch/push, owner credential use, native CALF record writes or commit/push occurred.

Contracts: [Git Trees](https://docs.github.com/en/rest/git/trees#get-a-tree), [Git blobs](https://docs.github.com/en/rest/git/blobs#get-a-blob), [Git refs](https://docs.github.com/en/rest/git/refs#get-a-reference), [annotated tags](https://docs.github.com/en/rest/git/tags#get-a-tag), [Git commits](https://docs.github.com/en/rest/git/commits#get-a-commit).

END
