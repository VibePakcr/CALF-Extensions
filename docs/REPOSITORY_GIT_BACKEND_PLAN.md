> Technical reference for the subordinate Git provenance/version layer. Follow the [project-map plan](REPOSITORY_LOCAL_GIT_PLAN.md) for product scope and implementation order. The earlier Git-focused phases below are not a standalone product plan.

# CALF Repository Navigator Local Git implementation plan

[한국어](REPOSITORY_LOCAL_GIT_PLAN_KR.md) · [CALF Extensions](../README.md)

Status: pre-implementation plan. Features and acceptance criteria here describe the proposed Local Git extension; they are not additions to the shipped FFmpeg preview's verified capabilities.

Add a free repository navigation extension to CALF Extensions. A developer opens one local repository, explores structure, changes and history, and follows the exact selected file version and line through code, Diff and an editor. Basic navigation requires Python 3.10+, installed Git and a browser, without a CALF core, SDK, account or AI API. CALF evidence and GitHub/GitLab service APIs are later stages.

## 1. Initial scope

| Capability | Behavior |
| --- | --- |
| Discovery | Distinguish ordinary repositories, linked worktrees, detached HEAD and unborn repositories. Observe the physical Git executable, version, object format, private Git directory and common directory. |
| Files | Tracked-file tree, path search, status filters and a selected commit's tree. Untracked content is opt-in; ignored content is excluded. |
| History | Commit parents, changed files, paged history, file history and rename candidates. Select the comparison parent for merges. |
| Changes | Separate HEAD→index, index→working file, HEAD→working file and explicit commit→commit comparisons. Keep conflict stages separate from ordinary staged files. |
| Map and inspector | Explore commit→parent, commit→changed file and directory→file edges. Below the map, show file information, code, Diff, identities, line navigation and editor links. |
| Navigation | Zoom/pan/fit, connection depth within loaded scope, back/forward, pinned comparison, panel collapse/height and version-bound navigation links. |
| Local viewer | An explicitly opened foreground loopback process reads selected files on demand. Closing it cleans up owned children, listener and temporary data. |
| Capture/export | Preserve JSON indexes and source captures in separate app data. Export offline HTML/JSON to a new folder; embedding captured source is optional. |
| Language and definitions | Explain HEAD, index, working file, merge parent and captures. EN/KO selection shows one UI language; code and commit messages remain original. |

Do not infer function calls, imports or runtime relationships from Git. Label the initial graph's actual relationship types. Do not ship VibePackr's retained GAPE data as analysis of another repository. Language analyzers are later extensions. File-role descriptions need referenced documentation, comments or explicit user mappings; otherwise show that no description is registered.

Detect bare repositories and promisor/partial clones and report them as unsupported in the initial version. Show accessible history and shallow boundaries for shallow clones. Show a submodule's gitlink and commit ID without recursive traversal. Identify LFS pointers without retrieving payloads.

## 2. Repository and version identity

Git has no universal repository ID shared by all clones. Create an extension `repository_id` in app data and require explicit registration/remapping of another clone or root. Remote URLs and branch names do not prove repository or version equivalence.

| Entity | Identity and display contract |
| --- | --- |
| Repository | Extension UUID; observed physical root, common Git directory and object format. Local paths are observations, not portable canonical IDs. |
| Worktree | Separate `worktree_id`, private Git directory, root, HEAD OID or unborn, and branch or detached state. Never mix worktree indexes. |
| Commit file | Repository ID + full commit OID + original path + blob OID/mode. Do not assume 40-character OIDs. |
| Index file | Stage 0/1/2/3, blob OID/mode and observed stage-list digest. Distinguish intent-to-add, deletion and conflict. |
| Working file | Independent capture ID, byte SHA256, size, capture time and display encoding for a regular file inside the physical boundary. Unread files have unknown SHA. |
| Comparison | Left/right kinds, commit/blob/capture IDs and paths; merge parent, rename settings, Diff representation and scope. |
| Graph edge | Type, endpoint IDs, provenance, analyzer version and scope. A commit/file edge never becomes a function call. |
| Coverage | Requested refs, paths and history scope; counts, exclusions, unsupported/truncated reasons, next page and boundaries. |

Rename detection is an observation at an explicit 50% Git similarity threshold. Retain original paths and OIDs; do not promote copy/rename candidates to permanent file identity. A merge defaults explicitly to parent 1 with other parents selectable. File history initially follows HEAD and exposes rename, shallow and merge boundaries.

Separate `schema`, `extension_version`, `git_version`, `repository`, `worktree`, `capture`, `nodes`, `edges`, `comparisons` and `coverage` in JSON. Keep labels, dates and descriptions separate from machine identity. Preserve recoverable original paths; undecodable paths receive escaped displays and explicit limitations.

## 3. Collection and refresh contract

Do not modify source, Git refs, index, configuration or original CALF records. Store output, cache and temporary files outside the inspected worktree and all related Git directories. Use platform app data, configurable with `--data-dir` or `CALF_REPO_HOME`; development and verification explicitly select T9 storage. Do not infer an existing `CALF_HOME` or records location.

Invoke the selected Git executable with argument arrays and `shell=False`. Disable pagers, color, optional index writes, fsmonitor, external diff and textconv. Use NUL-delimited paths, length-framed blob reads and literal paths. Do not run repository hooks, filters or commands. Compare raw blobs/index/captured bytes without confusing attribute transformations with original content. Revisions and paths remain validated data for fixed read operations.

Git status and raw byte differences are separate. A normal CRLF checkout can be Git-clean while differing from blob bytes. `status` and working-tree diff may execute attribute clean/process filters; do not assume they are harmless reads. P0 must exercise effective filters, attributes and submodule paths with sentinels and allow only commands with verified external-execution suppression. Where suppressing filters prevents Git-equivalent status, show `status_basis=RAW_BYTES` and the reason. Never fill unknown status with clean or infer Git-dirty solely from raw differences. Aggregate state includes coverage and unknown counts. Never change trust settings such as `safe.directory` automatically.

Discovery must verify actual Git capabilities and document the minimum supported version. The observed development-host Git 2.54.0 does not establish a cross-platform minimum. Detect promisor configuration and missing objects before operations that could trigger lazy fetch. Navigation exposes no fetch, clone, checkout, add, commit, push, configuration changes or tool installation.

Compare HEAD, refs and stage listings before/after metadata collection. If changed, retain `SOURCE_CHANGED` rather than publishing a consistent completed capture. Read working files on demand using stable regular-file reads and byte hashes, preserving separate file captures. Do not claim an atomic snapshot of an entire directory. Label older captures and separately report a changed current file.

Publish captures create-only under new IDs. Interrupted, partial or incomplete work never replaces the last complete capture. Do not retry automatically. Preserve initial failures and cleanup outcomes separately. Explicit refresh creates a new capture; do not add a filesystem watcher service initially.

Initially support UTF-8 and UTF-8 BOM. Preserve bytes, line endings and final-newline state; never synthesize source with replacement decoding. Classify binary, other encodings, oversized/missing objects and symlinks. Git symlink blobs may be shown as link strings; never follow working-file links. Do not present conflicts as successful merges.

## 4. Viewer and execution flow

1. `open` validates the repository/data directory and presents a lightweight shell first. Show HEAD, branch, dirty state, observation time and scope.
2. A common top menu reaches files, changes, history, map and export. State search/filter scope explicitly.
3. Selecting a file updates the inspector below the map with version, SHA/OID, line-numbered code, comparison bases, Diff, file history and editor links.
4. Selecting a commit/edge reaches the relevant parent, changed file or exact source. Reject or clear mismatched node/edge/version URL state.
5. Restore selection, comparison, filters, depth, pinned file, code line, camera center and zoom together. Same-document hash navigation follows the initial-load contract.
6. Editor opening is a user click. Separate current-file and captured-copy targets, support documented editor URIs and provide path/line copy fallback.
7. Closing the viewer cleans up its runtime; retained captures remain.

Expand directory/file/commit relationships progressively. Never describe 200 loaded commits as the entire history. Distinguish displayed, indexed, excluded and next-page counts. Render large lists and code in pages/windows: initially 200 commits per history page and 200 code lines per window.

Bind the foreground server only to `127.0.0.1` on an ephemeral port with a per-launch access token and Host/Origin checks. It is not an arbitrary filesystem or command server. Requests use registered repository IDs and validated relative paths/OIDs; reject external origins, traversal and remote binding. No wildcard CORS, CDN or external scripts. Keep tokens out of logs/exports. Source, messages and filenames remain non-executable data.

The following CLI is proposed, not implemented:

```text
calf-repo open --repo PATH [--data-dir PATH] [--git PATH]
calf-repo scan --repo PATH --data-dir PATH
calf-repo export --data-dir PATH --capture ID --output NEW_DIRECTORY [--include-source]
```

`scan/export` write one UTF-8 JSON response to stdout and bounded progress/diagnostics to stderr. `open` emits a token-free READY response and remains foreground; normal viewer termination does not imply successful source collection. Extension capture states do not impersonate CALF's `SATISFIED/UNKNOWN/VIOLATED`.

| Exit | Meaning |
| --- | --- |
| 0 | scan/export complete within declared scope, or clean viewer termination |
| 1 | Operational, input or cleanup failure |
| 2 | CLI syntax error |
| 3 | Partial result due to limits; coverage/reason required |
| 4 | Unsupported repository/tool capability |
| 5 | Source changed during collection; no complete publication |
| 130 | Cancellation with owned-resource cleanup confirmed; failed cleanup uses 1 and preserves both outcomes |

`scan` produces JSON without opening a browser. `export` uses only the selected capture; it does not reread source or update Git. Source is excluded by default. Before including source, show selected/captured coverage and exclusions. Exclude SDK records, credentials, Git configuration, absolute roots and editor-local paths by default. A shared export needs an explicit local path mapping for editor integration.

## 5. Implementation structure and reuse

```text
calf_extensions/repository/
  cli.py                 open / scan / export
  git_reader.py          bounded Git reads and subprocess lifecycle
  model.py               repository/version/edge/coverage contracts
  capture.py             stability checks and create-only captures
  compare.py             HEAD/index/working and commit comparisons
  viewer.py              foreground loopback read API
  export.py              offline JSON/HTML
  assets/                generic HTML/CSS/JS and EN/KO strings
  schemas/               index/capture/comparison contracts
  tests/                 unit and actual Git fixture checks
```

Extract map controls, inspector, code/Diff rendering, history and state links from the existing source-map experience. Do not distribute VibePackr paths, product code, captured source, GAPE data or T9 policy. Keep the new CLI separate from `calf-media`; basic execution must not import `calf_sdk`. Add no third-party Python/Node runtime dependency or FFmpeg requirement. Use installed Git/browser.

Release preparation adds the entry point, package data, EN/KO usage and a separate repository verification summary. Existing FFmpeg verification, checksums and release records are not evidence for this extension. Do not change or bundle the core/SDK/license files. Retain the free extension licensing boundary.

## 6. Implementation sequence and phase exits

| Phase | Deliverables | Exit condition |
| --- | --- | --- |
| P0 Contracts | Git capability matrix, read-command allowlist, schemas, failure/partial CLI contract, loopback lifecycle design | Classify normal/worktree/unborn/detached/shallow/partial/bare fixtures; observe no implicit network or external execution |
| P1 Collection | Repository/worktree identity; tree, stages, status, parents, boundaries, pagination and JSON | Collector criteria in LG01–LG06, LG09–LG11, LG14–LG17 and LG20 |
| P2 Source/comparison | Blob/index/working captures; four comparison types; conflict, rename, merge and binary states | LG07–LG13, LG17, LG19 and LG20; source hashes and Diff reconstruction match |
| P3 Viewer | Actual loopback API, map inspector, languages/search/history/editor | UI/API criteria LG18, LG21–LG24 and LG26; exact version-mode displays |
| P4 Export | Capture-bound offline HTML/JSON, selected source scope and portable paths | LG14, LG17, LG19, LG21 and LG25; reopen with network blocked |
| P5 Release readiness | Actual three-OS records, install/package data, EN/KO docs, regression report | Applicable LG01–LG28 criteria; existing media checks and isolation/preservation |

Each phase's output feeds the next. Freeze data/API meanings before collector and UI implementations diverge. Packaging, public publication and remote push are separate execution steps, not part of preparing this plan.

## 7. Acceptance criteria

Use new fixture repositories, separate app data and an explicit Git executable. Define fixed bytes, commits, expected stages and parents before running the extension; compare independent Git queries, direct hashes and browser displays. The collector's own output is not the sole oracle. Every item below is a future implementation acceptance criterion.

| ID | Scenario | Required result |
| --- | --- | --- |
| LG01 | Clean repository | refs/HEAD/tree/tracked files/blob/modes match independent Git; no dirty state introduced |
| LG02 | Two worktrees | Shared common directory and distinct private index/HEAD are identified; changes never cross worktrees |
| LG03 | Unborn/detached | No fake HEAD or empty failure before first commit; detached exploration uses exact OID |
| LG04 | Branch/tag/refresh | Preserve observations before/after ref movement; old links retain original OIDs |
| LG05 | Commit DAG/merge | Preserve both parents; selected-parent Diff matches Git; root-commit empty-tree comparison is correct |
| LG06 | Shallow/scope/paging | Show boundaries, next page and requested scope; pages join without omissions; no false complete-history claim |
| LG07 | Staged plus unstaged | Preserve HEAD A, index B and working C separately; all three comparisons use their exact bytes |
| LG08 | Create/delete/mode/rename | Distinguish additions/deletions/executable-bit changes/intent-to-add/rename candidates; preserve settings and original paths |
| LG09 | Conflicts | Separate stages 1/2/3 and working file; no successful-merge or ordinary-staged claim |
| LG10 | Paths | Preserve spaces/Korean/case/tabs/newlines/leading hyphens without command interpretation; OS-impossible names receive explained N/A |
| LG11 | Object formats | Actual SHA-1 and SHA-256 fixtures on supported Git; no 40-character assumption; reject unsupported tools under the minimum-version contract |
| LG12 | Text/newlines | Preserve UTF-8/BOM, CRLF/LF and final newline; code/hash match; Diff reconstructs target text and separately identifies newline-byte differences |
| LG13 | Non-text/links | Explicit binary/non-UTF8/oversized/LFS/symlink/submodule states; no link traversal or payload retrieval |
| LG14 | No mutation | Before/after refs, index bytes, tracked/selected-untracked files and configuration/attribute/hook hashes match; no output inside inspected roots |
| LG15 | No implicit execution/network | Zero sentinel hook/fsmonitor/ext-diff/textconv/clean-process-filter/credential-helper calls and remote connections; malicious names/messages render only as data |
| LG16 | Unsupported/missing | Explicit partial/promisor/bare/invalid/missing-object classification; no fetch/clone/automatic repair or false empty success |
| LG17 | Concurrent edits/partial result | Injected HEAD/index/file changes prevent complete publication; initial error and last complete capture survive; file timestamps remain distinct |
| LG18 | Foreground API | Listen only on loopback; reject invalid token/Host/Origin/ID/path; no write or command execution route |
| LG19 | Timeout/cancel/limits | Enforce time/output/source limits; owned children and ports gone within 5 seconds after cancellation; preserve cleanup and primary failures separately |
| LG20 | Comparison identity | Reject mismatched file/node/edge/version requests; never label stale source as a current checked version or current line |
| LG21 | Code/Diff/offline | Exact displayed lines and comparison bases; offline export opens without original repository and invents no missing content |
| LG22 | State/accessibility | Restore initial/same-document hash, back/forward, pin, filter and camera; keep keyboard focus and source/UI language boundaries |
| LG23 | Editor | Validate URI/path/line and actually open on supported platforms; separate current/captured targets; export omits original absolute paths |
| LG24 | Width/language | Desktop 1440 and mobile 390/320px have no page overflow; code scrolls independently; no mixed EN/KO UI, mojibake or console errors |
| LG25 | Export scope | New output directory only; accurate default no-source/selected-source coverage and exclusions; no credentials/config/SDK records/absolute root/access token |
| LG26 | Scale/performance | Observe the fixed 10,000-tracked-file/20,000-small-commit fixture on each platform, initially loading 200 commits; meet budgets below |
| LG27 | Package/regression | Fresh-folder install includes assets/docs/CLI; Git navigation works without SDK/FFmpeg; existing media checks/package functionality remain intact |
| LG28 | Actual platform evidence | Retain actual macOS ARM64, Windows x64 and Linux x64 Git/browser results, versions and artifact hashes; simulations do not qualify a platform |

Initial LG26 targets on local SSD with the same fixture: shell within 1 second, first metadata page within 10 seconds, warm opening of captured text up to 1 MiB within 1 second, and warm Diff within 2 seconds. Render at most 500 map nodes and 200 code lines at once by default. Target peak RSS of 512 MiB for the extension process tree (Python viewer and owned Git children), excluding the browser. Report the maximum of five comparable runs with conditions. Any revised target requires recorded cause, measurements and rationale; do not silently relax targets to match a failing implementation.

Initial resource limits: 30 seconds per Git command, 120 seconds per metadata collection, 16 MiB stdout/256 KiB stderr per command, 1 MiB preview per source file, and 64 MiB embedded source per export. Report exclusions/partial scope when source/list limits apply and let the user request narrower scope. History pages and visible-node limits are explicit loading boundaries, not silent data deletion.

## 8. Acceptance and subsequent integration

Accept the Local Git preview only after verification, preservation, actual UI review and aligned EN/KO documentation. Unexecuted criteria remain PLANNED/NOT_RUN, failures FAIL, and OS-impossible fixtures have reasoned N/A. Do not copy one OS's PASS to another. Record actual Safari/Chromium-family coverage separately. If CALF supervises implementation checks, retain the official native verdict bound to current contract inputs; command exit alone does not establish completion.

Subsequent CALF integration uses SDK 0.2.1 `tasks/inspect/changes` for evidence provenance and versions. The current list is limited to 32 recent jobs; task/attempt/recovery changes differ from working-tree Git Diff. Do not bypass those boundaries by reading core journals/SQLite or converting CI success into CALF success. GitHub/GitLab add PR/MR/CI adapters over the same repository model.

