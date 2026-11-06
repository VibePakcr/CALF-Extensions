# GitHub/GitLab project navigation implementation plan

[한국어](REPOSITORY_HOSTED_PLAN_KR.md) · [Acceptance JSON](REPOSITORY_HOSTED_ACCEPTANCE.json) · [Local Git plan](REPOSITORY_LOCAL_GIT_PLAN.md)

Baseline: `66bdf4a6e8d19ec87b4a10b9e541f1fe3870dc02` · 2026-11-07 · **H0–H5 scoped public/desktop qualification; private/full matrix remains incomplete**

See [H0 implementation](REPOSITORY_HOSTED_H0.md) for common contracts and [H1 implementation](REPOSITORY_HOSTED_H1.md) for manual registrations, credential references, bounded HTTP and cancellable identity probes. [H2](REPOSITORY_HOSTED_H2.md) adds the GitHub pinned reader with scoped anonymous public qualification. [H3](REPOSITORY_HOSTED_H3.md) adds GitLab pinned trees/raw blobs with scoped public retained-blob checks. [H4](REPOSITORY_HOSTED_H4.md) adds common source selection, maps, code/Diff, history, editor copies and v2 offline export with macOS Git-backed provider UI fixtures. [H5](REPOSITORY_HOSTED_H5.md) records real public providers, three desktop OSes, clean macOS installation and scoped measurements. Private and full-matrix qualification remain incomplete.

## 1. Goal and initial scope

Explore explicitly registered GitHub/GitLab repositories through the existing project map and the description/code/Diff panel below the whole map. Git supplies exact versions/content; features, documents and source relationships remain the main navigation path.

Start with public/private GitHub.com and GitLab.com repositories, branch/tag/full-commit selection, explicit refresh and two pinned commits within one repository. Account/org discovery, automatic registration, clone/checkout, remote writes, PR/MR/CI integration, Enterprise/Self-Managed and Rust/JS/TS call analysis are outside the initial scope. Reuse Python AST, document links and explicit feature/glossary mappings.

Flow: select a registered repository → choose branch/tag/commit → collect content/map → select a node/edge → inspect below-map details/code → choose comparison sides → inspect Diff. Collection starts on explicit request; authentication does not authorize scanning other repositories.

## 2. Existing boundaries to separate

| Current implementation | Planned change |
| --- | --- |
| `viewer.Project` constructs `GitReader` and local `Store` | Source-specific construction and a common snapshot |
| `analyze` consumes local `root` and `source(..., working)` | Analyze immutable snapshot content without importing/executing project code |
| `capture` requires worktree/index/local paths | Preserve a local v1 adapter and distinguish remote v2 captures |
| `compare`, API and export assume head/index/working | Explicit revision pairs and source capabilities |
| UI state centers on capture; export checks local paths | Registration/snapshot/navigation identities and provider-aware export boundaries |

Do not manufacture local directories or indexes to fit hosted data. H0 establishes the actual boundary and proves existing Local Git behavior still works.

## 3. Common data contracts

```text
Registration = {id, provider, api_origin, stable_repo_id, canonical_web_url,
                ref_kind, ref_name, credential_ref?, project_map_ref?}
Revision = {repository_key, requested_ref, resolved_commit, tree_oid?,
            observed_at, object_format_status}
Snapshot = {schema:v2, source_kind, registration_id, revision, inventory,
            content_manifest, coverage, captured_at, predecessor?}
Navigation = {snapshot_id, navigation_id, mapping_digest, analyzer_version,
              nodes, edges, provenance, coverage}
Content = {path_id, mode, provider_blob_oid?, byte_sha256?, size?,
           availability, kind, encoding?, raw_bytes?}
CompareContext = {repository_key, left_revision, right_revision, basis,
                  left_inventory, right_inventory, changed_paths, coverage}
Capabilities = {working,index,conflict_stages,immutable_revision,
                provider_permalink,cached_copy_editor,offline_export}
```

`repository_key` combines provider, API host and stable repository ID. Names/URLs are mutable display properties. Do not automatically merge similarly named local/remote repositories. `registration_id` is a separate app-data identity.

Store ref kind separately from its name. Resolve it once to a full commit at collection start, then read only that commit/tree/blob. A moving branch cannot mix revisions; a later refresh creates a new capture. When the GitLab API does not expose a Git tree OID, retain null with a reason. A normalized inventory digest is not a Git tree SHA.

Define `navigation_id = hash(snapshot_id, mapping_digest, analyzer_version, graph_schema)` to distinguish changed mappings/analyzers over identical code. Read existing v1 captures/navigation/bookmarks through a compatibility path without rewriting their files. Store successors separately and immutably.

Content availability distinguishes `READY / ABSENT / NOT_FETCHED / UNAVAILABLE / LIMIT_EXCEEDED / IDENTITY_MISMATCH`. An empty file is READY with zero bytes and its real SHA256; only a complete pinned inventory proves absence. Preserve provider OIDs separately from raw-byte SHA256. Do not guess object-format verification when the algorithm is unknown.

## 4. Provider reads and official contracts

| Operation | GitHub | GitLab |
| --- | --- | --- |
| Identity | Resolve the specified repository and retain stable ID | Resolve the specified namespace/project, then use numeric project ID |
| Ref pinning | Branch/ref, annotated-tag dereference, Git commit/tree | Branch/tag commit identity and commit lookup |
| Inventory | Git Trees for a pinned tree; subtree traversal when truncated | Repository tree at pinned commit; validated keyset/next pagination |
| Content | Read the tree-selected Git blob; decode Base64 and verify bytes/OID | Use the selected blob OID with the **raw blob endpoint** |
| Comparison | Common two-snapshot inventory/content comparison | The same comparison engine |
| Effects | Allowlisted read endpoints only | The same policy; arbitrary GET is not permitted |

GitHub recursive trees report truncation and Contents directory listings have a separate limit. Inventory completeness must be established explicitly. [Trees](https://docs.github.com/en/rest/git/trees#get-a-tree), [Contents](https://docs.github.com/en/rest/repos/contents#get-repository-content).

**GitLab JSON file/blob responses can transcode some encodings to UTF-8.** Use raw blobs for byte provenance and compare against an independent local fixture. [Raw blobs](https://docs.gitlab.com/api/repositories/#retrieve-raw-blob-content), [Files](https://docs.gitlab.com/api/repository_files/#get-file-from-repository).

Handle GitLab tree pagination and missing paths according to their API contract; missing total-count headers do not prove completeness. [Tree API](https://docs.gitlab.com/api/repositories/#list-all-repository-trees-in-a-project), [Pagination](https://docs.gitlab.com/api/rest/#pagination).

At H0 confirm and pin a supported GitHub API version constant, recording it in fixtures/live qualification. GitLab uses v4 endpoints and observed capabilities. Avoid beta/feature-flag-only APIs and archive/LFS expansion dependencies.

## 5. Code and Diff semantics

The required comparison is **direct comparison between two immutable snapshots**. Compare the union of complete pinned inventories by path/mode/blob, then obtain exact file bytes for common textual Diff. Initially offer the selected commit's first parent as a labeled default left side; a parentless commit compares against a proven empty starting state. Users can choose both sides.

Provider compare/patch responses are hints, not a substitute for inventories or original bytes. Account for GitHub compare file limits and GitLab `compare_timeout`, `collapsed` and `too_large`. [GitHub compare](https://docs.github.com/en/rest/commits/commits#compare-two-commits), [GitLab compare](https://docs.gitlab.com/api/repositories/#compare-branches-tags-or-commits).

Direct and merge-base comparison have separate bases. Direct comparison is required initially; enable merge-base mode only after separate qualification. Never label a provider default as direct comparison without verifying its meaning.

Distinguish rename hints from proven byte identities. Uncertain correspondence remains addition/deletion. Deleted/renamed files are read through their comparison context, not fabricated as current-map files. Binary, unsupported encoding and unfetched content mean textual Diff unavailable, not an empty Diff.

## 6. Registration, authentication, HTTP and coverage

App-data registrations retain URL/ref/label and a credential **reference** only. Start with anonymous public reads and server-side environment-variable references. Do not accept secret token argv/URLs/browser fields/storage or auto-discover existing credentials. OAuth, keychain and gh/glab adapters are later work.

Qualify GitHub with selected-repository fine-grained Contents read and required Metadata read permissions. Use GitLab `read_api` for the full read endpoint set; a Files API `read_repository` permission does not establish access to every API. Do not request write access or automatically broaden scopes after failure. [GitHub permissions](https://docs.github.com/en/rest/git/trees#get-a-tree), [GitLab authentication](https://docs.gitlab.com/api/rest/authentication/), [File scopes](https://docs.gitlab.com/api/repository_files/#available-scopes-for-personal-access-tokens).

Transport uses known HTTPS API origins, repository identity and allowlisted endpoint/query templates. Credentials go only to their authentication origin. Revalidate pagination/redirect links against origin/endpoint/repository/pinned-ref constraints. Registration does not create an arbitrary URL proxy.

| Initial budget/policy | Proposed value and behavior |
| --- | --- |
| Content | 1 MiB/file, 64 MiB total; bound the actual stream too |
| Responses/map | 16 MiB JSON response, 32 MiB retained metadata, 50,000 nodes, 100,000 edges; exceeded coverage stays partial |
| Requests | At most 300/job, reduced by provider remaining budget; pages/retries count too |
| Time | Metadata 120s, content/analysis 180s, total 300s; budget exhaustion is not completion |
| HTTP | Sequential queue per origin/credential; 5s I/O timeout; immediate cancel acknowledgement, owned-request drain target <=10s |
| Retries | At most two retries for eligible transport/5xx GET failures, respecting provider delay constraints |
| Throttling | Return RATE_LIMITED and retry/reset time; no unbounded waiting/retry outside the job budget |
| Cache | Partition by registration/origin/repository/auth identity and pinned commit/blob; 304 needs a matching validated entry |
| Coverage | Separate inventory/source/analysis/diff counts and states, including candidates/exclusions/failures |

Follow provider throttling/conditional-request contracts. [GitHub best practices](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api), [GitLab REST](https://docs.gitlab.com/api/rest/).

Failure/cancellation/identity mismatch never replaces an active capture. Retain coherent partial captures separately; do not automatically activate one over a previous complete capture. A first partial result also exposes scope. Access revocation does not erase already retained bytes; cached views retain capture time and the access-failure state.

## 7. Shared UI and compatibility

Collection runs outside the active-payload lock. A job builds an owned candidate, exposes bounded progress, then publishes a consistent snapshot/navigation pair under a short lock after checking cancellation and selection generation. Other views keep the previous valid capture usable. Bound DNS/TLS shutdown too; use an owned cancellable worker process if the selected transport cannot interrupt those waits. Passing a read timeout alone does not qualify cancellation.

Add local-only collection job/progress/cancel routes with bounded typed JSON (initial body limit 8 KiB) and the existing loopback Host/Origin/bearer checks. They accept registered IDs and typed refs, never provider tokens or arbitrary fetch URLs. Keep the existing Local Git CLI and refresh contract working. A local POST that controls collection does not authorize a provider POST/write. Credential-session cache partitions reset when the credential changes; retained source viewing remains explicitly historical.


The source selector lists Local/GitHub/GitLab registrations and adds remote branch/tag/commit and comparison-side selection. Node/edge selection synchronizes descriptions/features/code/lines/SHA below the whole map. Changing code version does not silently reanalyze the graph; explicitly request analysis of another revision. A late response cannot overwrite the newer selection.

Remote sources have no index/working/conflict-stage controls. Provider permalinks pin a commit. Editors open an explicitly retained copy or an explicitly bound local file with matching commit/blob identity. A retained copy is not a remotely writable path. A cached editor filename uses a safe local name/content identity, not an unchecked remote path. Display source and repository documents as escaped text, never active project HTML/scripts; unsupported encodings remain explicit rather than lossy replacement text.

Export uses retained content/comparisons only. Source remains opt-in; origin URLs and private names need separate explicit inclusion. Default projection retains an opaque source key and byte evidence. Exclude credentials/references and personal paths; record inclusion coverage in the manifest.

`sources add/list/remove/check` and `probe --source` are implemented in H1; see its guide for identity-only semantics and data-directory options. H4 implements `open/scan --source` and retained `open/export --view`; see [H4 usage and qualification](REPOSITORY_HOSTED_H4.md):

```text
calf-repo sources add --provider github --url https://github.com/OWNER/REPO --credential-env MY_GH_TOKEN
calf-repo sources add --provider gitlab --url https://gitlab.com/GROUP/SUBGROUP/PROJECT --credential-env MY_GL_TOKEN
calf-repo sources list
calf-repo open --source SOURCE_ID --ref-kind branch --ref main
calf-repo scan --source SOURCE_ID --ref-kind branch --ref main --project-map CONFIG_FILE
```

Keep existing `open/scan/probe --repo ...` and `export --data-dir ... --capture ...` behavior. `--repo` and `--source` are mutually exclusive. Unregistering does not automatically delete retained captures; deletion remains a separate user choice.

## 8. Implementation sequence and exits

| Phase | Deliverable | Exit |
| --- | --- | --- |
| H0 | Reader/DTO/capabilities, v2 capture/comparison contract and local adapter | HG03/04/08/10 contract fixtures, Local regression and unchanged v1 files |
| H1 | Manual registrations/env references, bounded HTTP/cache, progress/cancel jobs | HG01/02/16–20 transport fixtures without external services |
| H2 | GitHub identity/ref/tree/blob reader | HG05/07/09/11 and pinned live public GitHub qualification |
| H3 | GitLab identity/ref/tree/raw-blob reader | HG06/07/09/11 and pinned live public GitLab qualification |
| H4 | Shared map/inspector/Diff, change inventory, history, editor/permalink and offline | HG10/12–15/20–25 with visible source capabilities/coverage |
| H5 | Public/private, three OSes, browsers, package, performance and preservation report | HG26–32 plus actual outcomes/limits for the entire matrix |

H0–H4 are implemented with scoped macOS evidence, including prior public GitHub/GitLab reader checks and fresh H4 Git-backed provider browser fixtures. H5 public/desktop scope is now qualified; see its [outcomes and remaining limits](REPOSITORY_HOSTED_H5.md). After public H2/H3 navigation works, qualify private access through the same contract. Missing private/Enterprise/physical-device/editor evidence stays NOT_RUN and narrows support claims. The previous Windows POSIX-only skipped check is not resolved by hosted-source success.

## 9. Expected code impact

| Target | Scope |
| --- | --- |
| New `providers/base.py`, `providers/local.py` | Reader/DTO and existing Local Git adapter, without a dynamic plugin loader |
| New `providers/github.py`, `providers/gitlab.py` | Fixed API readers, without separate provider-specific map renderers |
| New `registrations.py`, `http_reader.py` | App-data registrations/env references and bounded HTTP/cache/request policy |
| `capture.py`, `analyze.py` | v1 compatibility, v2 retention and common snapshot analysis |
| `compare.py` | Revision pairs, inventory unions and exact-byte textual Diff |
| `viewer.py`, `cli.py`, `assets/*` | Source capabilities, async collection state, selection identity and common UI |
| `export.py`, `schemas/*`, `tests/*`, EN/KO docs | Provider-independent offline rendering, origin separation, fixtures and evidence |

## 10. Acceptance matrix

Every item is NOT_RUN. HG27/28 require actual provider qualification, distinct from mocks. HG13 merge-base mode is optional: direct comparison is mandatory, and unimplemented modes stay hidden. HG24 qualifies only the editor-target mechanism actually offered.

| ID | Phase | Scenario | Observable pass condition |
| --- | --- | --- | --- |
| HG01 | H1 | Explicit registration scope | Only the registered repository is requested; no user/org/project enumeration or automatic fork/submodule registration. |
| HG02 | H1 | Repository identity and URL resolution | Provider + API host + stable repository ID isolates similarly named projects; GitLab subgroups and renames preserve identity; a changed ID is refused. |
| HG03 | H0 | Ref pinning under concurrent changes | All reads use resolved commit A even if the branch moves to B; new refresh creates B separately; no mixed capture. Branch/tag name collisions and annotated tags resolve explicitly. |
| HG04 | H0 | Local compatibility and immutable capture migration | Existing CLI commands and v1 capture/navigation bytes remain usable and unchanged; remote captures contain no fictitious worktree/index/Git directory. |
| HG05 | H2 | GitHub tree truncation | A truncated recursive response expands subtrees within budget, or reports partial inventory; a directory over 1,000 entries never relies on Contents listing. |
| HG06 | H3 | GitLab pagination and missing paths | Follow validated next links/cursors; duplicate pages, loops, missing expected metadata and budget exits stay explicit. A 404 is never an empty successful tree. |
| HG07 | H2-H3 | Raw blob identity | Raw bytes, size and SHA256 match an independent local fixture; GitHub blob OID verifies; GitLab raw blob reads preserve non-UTF8 bytes without JSON transcoding. |
| HG08 | H0 | Zero bytes versus absence versus unavailable | Empty text has its real hash; deletion is inferred only from a complete pinned inventory. NOT_FETCHED, denied, oversized and corrupt content cannot become empty files. |
| HG09 | H2-H3 | Symlink, submodule and LFS boundaries | Modes and LFS pointers remain explicit; no target traversal, archive extraction, Git filters, project import or code execution occurs. |
| HG10 | H0-H4 | Local/provider graph equivalence | The same fixture commit produces the same normalized file/symbol/document/call relationships, lines, descriptions and explicit feature mappings across all three sources. |
| HG11 | H2-H3 | Path encoding | Spaces, Korean, +, %, #, tabs/newlines, slash refs and distinct Unicode spellings keep exact identity. Unrepresentable path bytes are unsupported gaps, not replacement paths. |
| HG12 | H4 | Complete changed-path inventory | A fixture with 350+ changed files is derived from both complete pinned trees even when provider compare omits entries; partial trees cannot claim a complete list. |
| HG13 | H4 | Direct versus merge-base comparison | A diverged-branch fixture shows distinct A-to-B and merge-base-to-B results; labels and pinned endpoints match the selected mode. |
| HG14 | H4 | Exact per-file Diff | Adds/deletes, rename hints, mode changes, binary, BOM, CRLF and final-newline differences retain both path/commit/hash identities; no patch means no invented zero diff. |
| HG15 | H4 | Independent coverage dimensions | Inventory, fetched sources, supported-language analysis and changed paths have separate counts/states; static links never become runtime/CALF success. |
| HG16 | H1 | Access and authentication failures | Missing environment, 401, permission/rate-limit 403, private-or-missing 404 and empty repository remain distinct; access failure never overwrites a retained capture. |
| HG17 | H1 | Credential containment | Canary credentials appear only in the correct outbound authentication header; none in argv, registry, logs, browser payload/storage, links, cached content or exports. |
| HG18 | H1 | HTTP destination and endpoint policy | Only configured HTTPS API origins and read endpoint templates are reachable; malicious next/redirect URLs, cross-project cursors and side-effecting GET endpoints are refused. |
| HG19 | H1 | Rate limits and conditional cache | Honor provider retry/reset timing without early retries; 304 requires matching cached content and auth partition; no unlimited retry, stale-to-fresh promotion or cross-registration leak. |
| HG20 | H1-H4 | Bounds, cancellation and late responses | Oversized/truncated bodies, stalled DNS/TLS/reads, cancellation and reverse-ordered responses remain bounded; canceled jobs publish nothing and late results cannot replace a newer selection. |
| HG21 | H4 | Map-to-inspector consistency | Node/edge selection ties description, feature, exact code line, source hash and graph revision together below the whole map; version changes never silently rebind the graph. |
| HG22 | H4 | Navigation identity and restoration | History/pins/zoom/language/ref/Diff sides restore for the same registration, snapshot and navigation ID; another source or mapping digest cannot inherit those bookmarks silently. |
| HG23 | H4 | Remote version capabilities | Remote views expose selected commit and comparison sides; local index/working/stage controls are absent. Provider links use verified repository URLs and pinned commits. |
| HG24 | H4 | Editor target identity | Open a labeled retained copy or an explicitly bound matching local file; verify commit/blob identity and line. Never invent a local checkout or a remotely writable path. |
| HG25 | H4 | Offline export | With networking blocked and originals hidden, retained map/code/Diff work within exported coverage. Source and origin inclusion are explicit; tokens and local/editor paths are excluded. |
| HG26 | H5 | Local/FFmpeg/CALF preservation | Repeat affected Local Git and FFmpeg contract checks; original sources, refs/index/config, v1 captures, FFmpeg release files and original CALF records retain their baseline hashes. |
| HG27 | H5 | Live public-provider qualification | Both providers return independently verified pinned fixture content and map/Diff observations; record API versions, counts and limits. Mock success alone cannot qualify either provider. |
| HG28 | H5 | Private-provider qualification | Verify an explicitly authorized private fixture and read access for each provider; unavailable live private evidence remains NOT_RUN and the published support claim is narrowed. |
| HG29 | H5 | Actual platform/browser qualification | macOS/Windows/Linux actual browser checks cover EN/KO, 1440/390/320 widths, code scrolling, zoom/pinch and no console errors; physical-device/editor tests stay separately labeled. |
| HG30 | H5 | Package and provider independence | Clean package installs include assets, schemas and CLI; Local Git works offline with no provider credentials or SDK/core/model imports; unrelated packs and records are preserved. |
| HG31 | H5 | Measured bounded performance | Record request/source/page budgets, cold versus cached timings and peak memory on a defined fixture. Target progress <=1s, cached opening <=2s, cancellation drain <=10s and peak RSS <=512 MiB. |
| HG32 | H5 | Read-only remote effects and evidence | Request audit contains only the chosen read endpoints; no remote writes, Git clone/fetch/push, webhooks, CI triggers or project-code execution. Incomplete/failed attempts and cleanup stay recorded. |

## 11. Independent evidence and verdicts

Explicitly register the same small synthetic repository through Local/GitHub/GitLab. Derive expected bytes/Git blobs/commits/modes/paths from local Git and independent byte hashes. Specify expected call/document directions and lines in the fixture, not by regenerating expectations from implementation output. Use HTTP fixtures for truncation, bad pagination, expired credentials, throttling, transcoded JSON content and slow/reverse-ordered responses.

Live tests read only registered test repositories. This plan does not itself execute private fixture creation, token issuance or remote changes. Distinguish public/private qualification, API connectivity/full UI behavior and cache/network observations.

Measure cold/cache behavior with fixture size, latency, request count and partial-collection scope. An example contains 10,000 inventory entries and 100 analyzed sources. Do not reuse the Local Git 10,000-file/20,000-commit result as hosted performance. The matrix values are targets, not measured results.

The regression baseline is the existing macOS/Debian 22 checks and Windows 21 plus one POSIX-only skip. Preserve FFmpeg checks/release files, original CALF records and owner settings. Distinguish this task's writes from concurrent changes; do not blindly restore another worker's changes. Missing qualification narrows the affected feature claim without adding a new blocker to existing releases.

Retain registration/pinned-revision manifests, credential-redacted request summaries, byte hashes, scoped outcomes, UI evidence and cleanup/preservation checks. Append predecessor/successor evidence rather than rewriting old failures or captures as successes. Provider/CI states do not become native CALF success or release authority.

END
