# H1 registrations, credential references, HTTP and cancellation

[한국어](REPOSITORY_HOSTED_H1_KR.md) · [Hosted plan](REPOSITORY_HOSTED_PLAN.md) · [Qualification](verification/repository-hosted-h1-20261107.json)

2026-11-07 · H1 implemented · macOS synthetic transport and Local UI regression verified

H1 adds manual GitHub.com/GitLab.com registrations and an explicit repository-identity check. Adding a source is local only: it does not contact the provider, resolve credentials, enumerate an account or collect code. Successful identity verification binds the stable provider repository ID; it does not establish complete code access, a fresh map or a successful release check. Hosted ref/tree/blob collectors and shared source-selection UI remain H2–H4.

## Register and check

Run from an installed extension or a checkout with the package on Python's import path. Keep app data outside source repositories and existing CALF records. Replace the uppercase placeholders. These commands use an already supplied server environment variable **name**, never a token value:

```text
python -m calf_extensions.repository.cli sources add --provider github --url https://github.com/OWNER/REPO --credential-env MY_GH_TOKEN --data-dir APP_DATA
python -m calf_extensions.repository.cli sources add --provider gitlab --url https://gitlab.com/GROUP/SUBGROUP/PROJECT --credential-env MY_GL_TOKEN --data-dir APP_DATA
python -m calf_extensions.repository.cli sources list --data-dir APP_DATA
python -m calf_extensions.repository.cli sources check SOURCE_ID --data-dir APP_DATA
python -m calf_extensions.repository.cli probe --source SOURCE_ID --data-dir APP_DATA
python -m calf_extensions.repository.cli sources remove SOURCE_ID --data-dir APP_DATA
```

Omit `--credential-env` for anonymous access. `sources check` and `probe --source` perform the same foreground identity probe; Ctrl+C requests cancellation and drains owned work. They return exit 0 for success, 130 for cancellation and a nonzero exit for failure. Ordinary `open/scan/probe --repo` and v1 export keep their existing interfaces. `open/scan --source` is not implemented.

The registry owns only `APP_DATA/registrations`, validates its schema marker, rejects Git-store output locations and keeps previous registration versions. Removal disables the registration and retains captures/history. Duplicate active provider URLs are idempotent only with the same credential reference; changing the reference requires remove and deliberate add. A stale lock returns `REGISTRY_BUSY`; it is not silently removed. Foreign registry namespaces and symlinks are refused.

Identity states are `REGISTERED_UNVERIFIED` and `IDENTITY_VERIFIED`. Verified renames retain the stable numeric ID; an ID change is refused. Visibility may remain unknown. GitLab's explicit `empty_repo` can establish EMPTY/NONEMPTY; GitHub `size=0` is insufficient and remains UNKNOWN. A 404 means `ACCESS_UNKNOWN`, including inaccessible private repositories, rather than empty or deleted.

## Authentication and HTTP contract

- Read a configured environment reference only when a request starts. Persist its name, not its value. CLI/browser responses expose only `credential_configured`; no token-entry field, token argument, URL credential, keychain lookup or gh/glab discovery is provided.
- The owned request subprocess receives the token through stdin and constructs only the correct authentication header. Its environment excludes credential variables and ambient proxy settings. No credential or response-body disk cache is added. A reflected credential in provider headers/body is refused before caching/publication.
- Production uses standard verified HTTPS to `api.github.com` or `gitlab.com/api/v4`. GitHub requests pin API version `2026-03-10`. There is no configurable fetch origin or TLS bypass. Test fixture injection exists only as a Python dependency.
- Allow only GET/HEAD identity, branch, tag, commit, tree and blob endpoint templates. Non-identity requests require a bound repository ID. No arbitrary GET proxy, provider writes, account discovery, clone/fetch or project execution is added.
- Validate redirects and pagination against origin, endpoint, repository and pinned ref. Follow only numeric identity redirects and GitLab tree pages within that scope. Cursor loops, altered scopes and ambiguous links fail explicitly.
- Use a shared per-origin request gate, 300 requests/120 seconds per default operation budget, 5-second I/O timeout and a 10-second owned-request deadline. Pages/retries inherit the budget. JSON responses are capped at 16 MiB; raw GitLab blobs at 1 MiB and encoded GitHub blob responses at 2 MiB. H2/H3 must still decode and verify original bytes.
- Retry eligible transport/5xx failures at most twice. Distinguish missing credentials, 401, permission-denied 403, rate limits and unknown-access 404. Return retry/reset time without unbounded background retry. Reject malformed/duplicate JSON, HTML, oversized and truncated bodies.
- Keep ETag bodies only in bounded process memory, isolated by reader registration/identity and credential session. A changed credential clears that partition. A 304 without its matching cache fails. Explicit retained H0 snapshots remain separate historical evidence.

## Local API and owned jobs

The existing foreground Local portal hosts these routes under its loopback Host/Origin/bearer checks. Registration/job operations do not hold the active project-map lock. POST requires typed JSON, `Content-Type: application/json`, one Content-Length and at most 8 KiB; token values and arbitrary fetch URLs are not accepted.

| Method | Route | Body / result |
| --- | --- | --- |
| GET | `/api/registrations` | Enabled public registration summaries |
| POST | `/api/registrations` | `{provider,url,credential_env?}` → unverified summary |
| POST | `/api/registrations/ID/remove` | `{}` → disabled summary |
| POST | `/api/jobs/probe` | `{source_id}` → identity job |
| GET | `/api/jobs/ID` | State, phase, completed request count and sanitized result/error |
| POST | `/api/jobs/ID/cancel` | `{}` → cancellation acknowledgement |

Job states are QUEUED, RUNNING, CANCEL_REQUESTED, CANCELLED, SUPERSEDED, SUCCEEDED and FAILED. Request counts are finalized when the job stops. Cancellation acknowledgement is distinct from stopped state: inspect until terminal. A new probe supersedes older probes for that registration. Cancellation, generation and registry-version checks precede identity publication; failed/cancelled/late results do not alter the active Local map. Shutdown cancels and joins owned jobs/processes and clears transient clients. Job state is bounded in memory and is not a CALF execution receipt or durable work queue.

## Observed qualification and limits

The final macOS repository suite passed **62 tests: 22 existing + 12 H0 + 28 H1**. The H1 fixtures exercise actual local HTTP subprocesses, authentication-header placement, scoped redirects/pages, credential echo/rotation, status/cache/budget/body failures, a stalled worker, cancellation/generation races, local API guards and continuing Local-map access during cancellation. A real local TLS server with an untrusted certificate was rejected. GitLab Unicode/plus namespaces are encoded exactly once; truncated identity bytes cannot become successful metadata.

Three FFmpeg contract checks passed. Fresh actual Chrome live/offline checks passed map/code/Diff, call lines, bookmarks, EN/KO, emulated pinch and 1440/390/320 widths with no runtime errors. The original fixture repository was hidden for offline viewing. Servers, listening sockets and owned test browsers stopped. No new hosted-source form/UI was added or qualified.

All **607 protected files** in the H1-start preservation set retained their hashes, covering existing FFmpeg/license/release files, historical v1 artifacts and the prior CALF preservation set. Existing shared README/package edits were unchanged. H0 source changed only at the intended CLI/portal integration points. Native CALF records were not written; no commit/push, real provider request, owner credential lookup or remote mutation occurred in this qualification.

Actual public/private GitHub/GitLab access, successful trusted public TLS, hosted collection/map/Diff/export, Windows/Linux H1, clean package installation, performance/memory qualification, physical phones and actual external editor launching remain **NOT_RUN**. Full HG01–HG32 acceptance remains NOT_RUN; the linked qualification adds scoped H1 fixture progress only. Next is H2's GitHub pinned-ref/tree/blob reader.

