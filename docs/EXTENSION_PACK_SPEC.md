# CALF Extension Pack Specification

[한국어](EXTENSION_PACK_SPEC_KR.md) · [Schema and examples](../specs/pack-v1/README.md) · [Home](../README.md)

**Specification 0.1.0 · Draft · 2026-11-07.** This defines a shared contract for the FFmpeg, motion-patch and Repository packs. The [first local implementation](PACK_MANAGER.md) supports FFmpeg candidate metadata, compatibility, locks, staging, qualification, activation and transaction recovery. A general dependency resolver, download registry and Workbench pack UI remain outside that preview. Existing releases and contracts are unchanged. A schema-valid manifest alone does not qualify a pack for installation or execution.

## 1. One small core, independently versioned packs

The core owns supervised execution, attempts, native evidence and adoption. Packs provide domain inputs, fixed tool adapters, independent checks, domain recovery and documentation through public interfaces. CLI, SDK and MCP share the same domain implementation. MCP is an optional interface; it grants no execution authority. A pack does not embed another engine or agent scheduler.

| Item | Rule |
| --- | --- |
| Pack identity | Stable lowercase dotted `id`; no user path or provider account in the ID. |
| Pack version | SemVer `MAJOR.MINOR.PATCH`, optional prerelease/build metadata. Released `(id, version)` always identifies the same package bytes. Changed bytes require a new version. |
| Compatibility changes | Breaking input/output, side-effect, permission or recovery semantics require a major pack version. Additive compatible features use minor; compatible fixes use patch. Record the change even for 0.x. |
| Schema | `calf.extension-pack.v1`; this draft is not yet a frozen deployed format. Once adopted, incompatible parsing/meaning changes require a new schema major. Unknown required fields/capabilities block activation. |
| Distribution | Pack version, monorepo/Python distribution version, SDK version and core edition/version are separate identities. Do not retroactively rename or rehash FFmpeg 0.1.0. |
| Maturity | `experimental`, `preview`, `stable`; maturity does not replace verification. Reference manifests use `availability: reference` and cannot be installed as releases. |

The draft now also distinguishes `availability: candidate`: an experimental/preview artifact that may be staged and locally qualified, then activated only with an explicit experimental selection. It cannot claim stable-release conformance. The three design examples remain non-installable references.

Breaking changes never rewrite existing work to match a new pack. Prerelease packs require deliberate selection; no implicit upgrades from preview to stable or between core editions.

## 2. Modes and dependencies

The manifest declares dependencies once and references them from each mode. Resolve **only the selected mode**, using already installed local tools or explicitly staged dependencies. Do not solve a global package environment or import every pack to discover its metadata.

| Pack / initial mode | Dependencies and core | Scope |
| --- | --- | --- |
| `calf.media.ffmpeg` / supervised scenes | Python 3.10+, SDK 0.2.1, FFmpeg/ffprobe with required encoders/filters; Harness 1.8.7 **or** Workbench 1.9.2 | Existing scene candidates, technical checks and scene selection. |
| `calf.media.motion-patch` / supervised patch | Separate NumPy/OpenCV environment, Python, SDK and compatible core | Proposed small background-patch alignment. FFmpeg is needed only for a separately selected comparison-preview mode. Nuke is an optional handoff, not a basic requirement. |
| `calf.repository.local-git` / standalone navigation | Python, installed Git with required capabilities, browser for the viewer; **no core, SDK, FFmpeg or model requirement** | Planned read-only Git collection/view/export. CALF evidence integration is a later optional mode. |

Dependency declarations include an ID, kind, bounded numeric version interval and required features. Intervals are `[minInclusive, maxExclusive)`, compared as integer version components, zero-padded for comparison. The first format accepts stable numeric tool/package versions, not arbitrary pip/npm expressions, prerelease matching or shell expressions. Keep the original vendor version string alongside its normalized version. Unrecognized versions remain `UNKNOWN`; use ecosystem metadata/capability checks or a later explicit format revision rather than guessing.

For Python libraries, inspect distribution metadata in the selected environment before importing native modules. Pin exact installed dependency versions and distribution/wheel hashes in its lock. A broad interval is a declared candidate range, **not evidence that every version in it works**. Tool features such as `libx264`, `blackdetect`, SHA-256 Git objects and disabled lazy fetch need independent capability observations.

A capability-only application dependency, such as a browser, uses `versionPolicy: capability-only` and mandatory feature names rather than an invented shared browser version floor. Record the actual browser/version and qualify only tested combinations. Repository inspection and offline export do not require the browser; the selected viewer mode does.

Core ranges are edition-specific alternatives. The FFmpeg reference initially uses `>=1.8.7 <1.8.8` for Harness and `>=1.9.2 <1.9.3` for Workbench. Widen them only with new evidence. No assumption that all 1.8.x/1.9.x builds or a newer SDK are compatible. Supervised modes require the documented public protocol and registered adapters; use a read-only probe when available, otherwise exact qualified binaries. Do not invent discovery endpoints, read private SQLite or create trial work during discovery.

Compatibility reports distinguish `COMPATIBLE`, `INCOMPATIBLE`, `UNKNOWN`, and `NOT_REQUIRED` for standalone modes. Missing dependencies, untested platform/core combinations and absent protocol evidence cannot produce a green ready state. A user may deliberately enter an experimental test mode with `UNKNOWN` clearly shown; that does not qualify a normal release or authorize new effects.

## 3. Package contents and local resolution lock

Proposed release layout:

```text
pack.json                  declarative manifest; UTF-8 JSON, at most 64 KiB
FILES.sha256               payload file inventory; excludes itself
qualification.json         platform/check scope, result and evidence identities
docs/                      English/Korean instructions and limitations
...                        pack code, static assets and bounded examples
```

The release's external SHA256SUMS covers the archive and separately supplied qualification files. A file hash establishes identity, not publisher trust. Verify the selected publisher/source independently; record the authenticated channel or signature when provided. Reference packages have no fabricated signatures or placeholder checksums accepted as evidence.

After staging, a future host writes a **local resolution lock**, outside immutable pack files and outside user source. It binds:

- Pack ID/version, manifest SHA-256, archive SHA-256 and payload inventory digest.
- Selected mode and capabilities; exact core edition/version/executable hash if required.
- Resolved interpreter, SDK/adapter files, tool hashes, library distribution lock and feature-probe results.
- Input/output/check schema and profile versions/digests; permitted roots, network policy and effective resource bounds.
- Qualification receipt references, platform/architecture, inspection time and explicit unknowns.

The host also pins this identity into new work's public contract/registration. Old work keeps its original contract and references. Do not edit old journals, reset attempts or silently substitute a newly installed tool. Hashing selected tools does not attest every OS/transitive library or create a filesystem sandbox.

No credentials, original records, source captures, videos, host-specific paths or user preferences belong in the distributable. Absolute local paths may exist in the private lock only. Packs do not bundle CALF core/SDK or third-party tools by default; redistribution needs its own license and size review.

## 4. Install, activate and update

The first FFmpeg-only implementation of this contract is documented in [Local pack lifecycle preview](PACK_MANAGER.md). There are no setup/install hooks or automatic dependency downloads.

1. **Inspect metadata:** parse bounded JSON without importing the pack or running setup scripts. Select the mode and show required dependencies and effects together. Reuse existing authorization; no per-file confirmation flow.
2. **Stage a new version:** verify archive identity/source; extract into a new private staging directory on the same filesystem as the eventual pack store. Never extract over an installed version.
3. **Check inventory:** reject absolute/traversing paths, symlinks/hardlinks/special files, duplicate or case-colliding names, Windows reserved/ADS paths, extra/missing files and hash changes. Initial installer ceilings: 64 MiB compressed, 256 MiB expanded, 4,096 regular files, 16 levels; stricter host limits win. These are design limits for pack payloads, not media-job limits or measured memory guarantees.
4. **Resolve the selected mode:** inspect local dependencies and platform evidence; record missing/unknown conditions. Do not download a model/tool, alter PATH, shell profiles, global Python packages, MCP client configuration, core settings or OS services automatically.
5. **Check in isolation:** run the pack's declared installation checks in a new scratch/records/project directory with synthetic inputs. Live provider calls, external transmission and user-data mutation are not installation probes. Fixed checks still need the host's existing execution authority.
6. **Activate for new work:** write and flush the new lock and atomically replace a small active-version pointer under a host lock, after identity recheck. Keep the old pointer/version. If atomic replacement/durability cannot be confirmed, retain the staged state and report an interrupted activation; inspect current state before another write.

Only new work uses the new active version. Existing jobs continue with their retained core, adapters, dependencies and records. A pack update must not interrupt a running worker, release an unresolved native slot or cause a second execution. Existing account/credential locations remain with their owner.

First adoption of this format is additive: wrap a future release with metadata and new registration. Do not modify the current FFmpeg archive, registration or frozen contracts in place. Keep the existing `calf-media` path usable. The draft does not require changing the shared Python distribution or its entry points now.

## 5. Verification and completion

Keep these three results distinct:

| Layer | Pass evidence |
| --- | --- |
| Package/compatibility | Complete payload hashes, selected-mode dependency/protocol observations, successful isolated install checks and exact platform evidence. |
| Work execution | For supervised work, current native `verified` and `SATISFIED`, with input, adapter/profile, candidate manifest and independent receipt identities bound. Exit 0 or an MCP handshake is insufficient. |
| Domain acceptance | Required technical/quality checks and the frozen adoption conditions are met for the exact candidate and unchanged protected scope. Human acceptance is separate when required. |

Use `PASS`, `FAIL`, `UNKNOWN`, `NOT_RUN`, and reasoned `N/A` in qualification records; include check ID, requested/observed scope, actual tool/core hashes, platform and provenance. Reused evidence retains its original identity/date. Do not copy one OS's pass to another or convert design targets into measurements. Pack lifecycle qualification is separate from existing FFmpeg runtime qualification.

FFmpeg continues to require its media checks and scene-project compare-and-swap. Motion needs held-out alignment measurements, preserved edit intent, unchanged pixels outside the authorized mask, temporal stability and no newly introduced distortion; unsupported content remains outside its pass claim. Repository needs exact HEAD/index/working/commit identities, scope/partial-result labels and before/after repository preservation. A standalone view is **not** native CALF verification.

No required check may be omitted or weakened after failure to obtain a pass. Check/input/tool/candidate drift invalidates the applicable current evidence; preserve the historical receipt. Default execution is a single requesting agent and one worker per existing native execution scope. Do not add a parallel scheduler.

## 6. Recovery and data preservation

| Event | Required behavior |
| --- | --- |
| Dependency missing/changed | Block the affected mode/new work; retain prior locks and work. Restore an explicitly trusted matching dependency or register a new version for new work. Never silently repair global settings. |
| Interrupted stage/activation | Keep first failure and staging receipt; inspect the active pointer and bytes under the lock. No blind replay or overwrite. |
| Lost execution response/timeout | Inspect/reconcile the same native request. Retain consumed attempts and unresolved reservations; timeout is not failed-job proof. |
| Cancellation | Confirm actual termination and owned-process cleanup; a request, missing PID or closed window is insufficient. Unconfirmed cleanup remains UNKNOWN. |
| Pack rollback | Select a retained, verified pack/lock **for future work**. Recheck it against the current host. Does not roll back work history, project state or user data. |
| Domain restore | Invoke only the explicitly declared domain path with current identity checks. FFmpeg can select retained scenes; motion-patch restore is not yet qualified. Repository reopens a retained capture; it never checks out/resets the source repository. |
| Uninstall/cleanup | Disable new use first. Keep versions/environments referenced by active, unresolved or resumable work. Remove only unreferenced code/cache through an explicit cleanup action; no silent record, candidate, contract, credential or preference deletion. |

CALF Universal Work v1 currently adopts only the current candidate; it does **not** expose general selection of an earlier adoption. FFmpeg's scene restore is a separate extension contract. Pack rollback, native recheck and domain restore must never be presented as interchangeable operations.

Store records, retained candidates and user settings outside the pack version directory. Snapshot/hash permitted preexisting data for update qualification; retain the original format and paths. Personal defaults may suggest parameters only for new work. Existing contract/profile/approval scope remains authoritative. Config migration is not part of v1: stage any future explicit, reversible migration separately, preserving its original.

## 7. Lightweight and local defaults

- Read a small manifest for discovery. Import only the selected mode's modules; keep OpenCV/NumPy out of Git navigation and FFmpeg-only execution.
- Run on demand. MCP uses foreground stdio; a viewer may use a foreground authenticated loopback listener. Close owned listeners/processes when the session ends. No resident pack daemon or automatic startup service.
- Load selected files/pages only, bound preview/log/cache sizes and stream large artifacts. Keep evidence on disk and load it by reference; do not preload media or complete histories. Evict only owned, unreferenced cache; original evidence is not cache.
- Declare operation time/output bounds and reuse the existing core resource fader. Optional preview/export work yields under pressure; never lower required checks. Thread-count hints and polling are not kernel CPU/memory quotas.
- Models and provider accounts are not required by these three packs. No runtime dependency download or network probe during discovery. Repository viewing is loopback-only; exports work offline. A future external mode needs explicit destinations/data policy and credential references outside the package.
- A cloud agent can receive MCP tool results even when execution is local. The host chooses that transmission scope; local file processing alone is not a no-data-leaves guarantee.
- UI defaults to English with Korean guidance; text/path/content handling preserves UTF-8 and CJK. Capture OS-impossible filenames as limitations, not fabricated portability success.

## 8. Common release acceptance gate

Record evidence per criterion, selected mode and platform. The local FFmpeg preview exercises installation, pinned dependencies, native work and interruption recovery; it does not promote every pack or every criterion to PASS. Schema validation is recorded separately, and unexecuted domain/platform/release checks remain NOT_RUN.

| ID | Required check |
| --- | --- |
| PK01 | Strict JSON/schema, unique IDs, valid intervals/references; reject duplicate keys, unknown security fields and reference manifests as releases. |
| PK02 | Corrupt archive, inventory mismatch, traversal/link/collision/oversize fixtures fail before activation; old active version remains readable. |
| PK03 | Missing tool/SDK, unsupported core/platform, unknown feature and offline state are explicit; zero implicit installs/network/settings changes. |
| PK04 | Standalone Repository discovery/execution imports no SDK, media/native CV dependency or model. Only selected-mode dependencies load. |
| PK05 | Fresh isolated install checks produce evidence for the installed bytes; foreground listeners/children end after close/cancel. |
| PK06 | Inject interruption before/after pointer replacement and lost replies; concurrent activation never yields mixed-version work. Preserve first failure. |
| PK07 | Update while old work is ready/running/unresolved; old identity/attempts resume intact; new work selects the new version without double execution. |
| PK08 | Pack rollback and uninstall preserve all referenced versions, locks, records, contracts, settings, credentials and domain approvals. |
| PK09 | Candidate/input/check/tool drift and normal producer exit without valid checks cannot permit adoption; denied calls create no unauthorized effect. |
| PK10 | FFmpeg scene invariants, motion quality/scope checks and Repository read-only/version checks pass their own criteria; unsupported domain recovery stays unavailable. |
| PK11 | EN/KO instructions, CJK paths, new-folder install, offline use and exact native core/SDK/adapter identity work on actual macOS/Windows/Linux within declared scope. |
| PK12 | Published artifact download/hash and source identity match on each destination; record exclusions and reused evidence. Schema/handshake checks are not full runtime qualification. |

Release promotion needs PK01–PK12 plus the pack-specific acceptance criteria for every claimed platform/mode. No new soak/memory benchmark is required by this design task; report resource bounds and any later measurements with their actual scope.

## 9. Applying the draft

1. Review the [three non-installable reference manifests](../specs/pack-v1/README.md) against their current pack plans. Keep experimental motion work and Repository P0 development separate.
2. Implement a small metadata/compatibility reader and local resolution-lock writer without importing packs or changing native execution semantics.
3. Add side-by-side staging/activation and recovery; run the common acceptance gate in isolated fixtures.
4. Attach qualified metadata to **new** pack releases. Add optional Workbench discovery over the same metadata and records; do not build a second manager/engine in the UI.

References: [current public Universal Work v1](https://github.com/VibePakcr/CALF/blob/main/SDK_WORK_PROTOCOL.md), [FFmpeg guide](FFMPEG.md), [Repository plan](REPOSITORY_LOCAL_GIT_PLAN.md). The schema covers manifest structure; cross-reference resolution, interval ordering, file identity, authorization and runtime correctness require host checks described above.
