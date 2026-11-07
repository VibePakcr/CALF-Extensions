# H5 public and desktop qualification

[한국어](REPOSITORY_HOSTED_H5_KR.md) · [Plan](REPOSITORY_HOSTED_PLAN.md) · [Evidence](verification/repository-hosted-h5-20261107.json)

2026-11-07 · H5 qualifies the public navigation path and the fixed desktop candidate. Private access and the complete provider/platform matrix remain incomplete. This is navigation evidence, with no release or CALF execution authority.

## Candidate and correction

Candidate r1 froze H0–H4 plus the existing package files before qualification. Actual GitHub source exposed an offline rendering defect: source strings containing `/*BOOTSTRAP*/`, `/*STYLE*/` or `/*SCRIPT*/` were interpreted by later template replacements. The exported bootstrap became invalid JSON/JavaScript.

The renderer now substitutes slots once in the original template. Inserted source and asset text remain literal. New tests round-trip all three markers, closing script text, Korean and Unicode line separators. Candidate r2 records that correction; r3 also makes the native Windows test fixtures portable. Earlier candidates and failures remain retained.

Windows control-byte paths are constructed in native Git tree objects without checking them out or disabling index protection; the same byte assertions remain. The cached CLI test labels Windows `TerminateProcess` cleanup separately from graceful console Ctrl+C. Production provider readers, analysis, source persistence and comparison remain unchanged from H4.

Final r3 manifest SHA256:

```text
b0e5dadc9e0e4f18f68e228f12f09ff849f3644d086b8eda6f0b44cc71772943
```

## Actual public providers

| Path | Actual scope |
| --- | --- |
| GitHub anonymous HTTP | Correctly retained a partial capture after API rate exhaustion; did not activate it as complete |
| GitHub via `gh` CLI | Existing CLI login; no token extraction/storage; full right/left inventories of 56/29 files and 85 retained byte checks against the same commits in independent local Git |
| GitLab anonymous HTTP | Full right/left inventories of 32/34 files and 66 native Git blob checks; 26/15 same-path blob matches against independent retained local Git |

GitHub commits were `66bdf4a6e8d19ec87b4a10b9e541f1fe3870dc02` and `620447ca5dab2020e19221cda363e9c2b36d1048`. GitLab commits were `814b6c27fe9ac68ad3f9bb6db7fe2e8ba95f65d1` and `01370f6ad5de62709afd70b4d9a431c95509c6e8`. GitLab has no root tree OID in this API contract; full same-commit local inventory equality was not established for it.

Both public paths exercised manual registration, identity check, branch pinning, map, below-map code/direct Diff, pinned provider links, retained editor-copy URI and exploration restoration in real Chrome. After the renderer correction, the exact retained inputs were replayed through the final renderer and exported with HTTP blocked. Original source text round-tripped exactly. Provider reads were not repeated merely to regenerate rendering evidence.

`gh` was used through a **qualification-only fixed-endpoint transport** around the unchanged GitHub reader, as requested by the owner. It is not a shipped `gh` credential adapter or automatic account connection. The shipped default HTTP/credential-reference behavior is unchanged. The successful CLI run does not erase the anonymous rate-limit result.

## Desktop, package and measurements

| Environment | Final candidate result |
| --- | --- |
| macOS / Python 3.12 | 123 repository checks passed; real Chrome public/cached/offline and independent Local Git/v1 regression |
| debian-work / Python 3.13.5 / Git 2.47.3 | 123 checks passed; actual Chrome common GitHub/GitLab fixture UI and offline |
| packr-win / Python 3.12.10 / Git 2.55 | 123 checks run: 121 passed, two explicit skips; actual Edge common fixture UI and offline |

Windows skips retain the unavailable native OpenSSL negative-TLS fixture and POSIX-only executable fixture. They are not converted to passes. Browser reports distinguish actual provider reads on macOS from Git-backed synthetic provider responses on the other OSes. EN/KO, 1440/390/320 widths, below-map code/Diff, delayed response isolation and retained editor-copy URI were checked. Separate desktop gesture checks cover code scrolling, pinch emulation, wheel zoom and keyboard panning; these are not physical mobile tests.

A new isolated T9 wheel build/install includes assets, schemas and `calf-repo`. Installed Local Git runs with networking blocked, no SDK present and no core/model imports. Build dependencies are pinned only in the new build environment. Nothing is published or installed into owner/system tool homes. The same wheel SHA256 was installed in fresh macOS, Debian and Windows environments. Remote installs were offline and used existing Python/venv tools; source-run browser qualification is separately identified. Existing FFmpeg contract checks also passed (3).

A defined 301-file, five-content synthetic fixture measured initial progress ~0.0002s, cold collect/analyze ~0.24s, retained-context/payload opening ~0.023s, cancellation drain <0.001s and service peak RSS ~40MiB. This meets the stated service targets for that fixture. Actual cached public portal reopen measurements are in the machine-readable report. External provider latency, browser aggregate memory and substantially larger workloads are not qualified by these numbers.

## Preservation and remaining scope

The final report binds source/candidate/helper hashes, actual provider request audits, byte checks, platform receipts, skipped checks, performance scope and cleanup. Preserve H0–H4 reports and prior v1/FFmpeg/CALF artifacts. All 607 protected files and 15 H0–H4 historical files matched their baseline hashes. No configuration was restored.

Still NOT_RUN: explicitly authorized private fixtures/permissions, Enterprise/Self-Managed, live public provider reads on Windows/Linux, native editor launch, physical mobile devices, Windows graceful console interruption, broad performance/memory qualification. The full HG01–HG32 matrix is not declared complete; scoped H5 outcomes are recorded separately. No repository commit/push, provider write, webhook/CI trigger or project-code execution is part of this qualification.

Concurrent README changes and a new pack-verification module from another work stream were left intact and excluded from this fixed navigation candidate.

