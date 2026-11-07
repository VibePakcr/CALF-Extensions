# Local pack lifecycle preview

[한국어](PACK_MANAGER_KR.md) · [Common specification](EXTENSION_PACK_SPEC.md) · [FFmpeg](FFMPEG.md)

The implementation reads v1 metadata, checks explicitly selected local dependencies, retains resolution locks, and stages/qualifies/activates local candidate packs. It uses Python's standard library: no JSON Schema runtime dependency, model, download service or daemon. The metadata reader interprets only the bundled v1 schema subset and rejects unsupported fields; it is not a general JSON Schema service.

This is a **local developer preview** released as separate Local Pack Tools; no Workbench pack-management UI is included. FFmpeg scenes and [Repository Local Git inspect](REPOSITORY_PACK.md) have separate lifecycle drivers. Repository inspect needs only Python and Git; it does not load the SDK or media tools. Motion and the planned Repository viewer modes return `UNKNOWN / driver_not_implemented`. Reference manifests remain non-installable. The `candidate` availability value allows isolated installation checks; it requires experimental/preview maturity and explicit experimental activation after successful local qualification. Stable release qualification remains a separate gate.

## 1. Select local paths

Run commands from the CALF Extensions source root. Use `python` on Windows, with physical Windows paths. A future installed distribution will also expose `calf-pack`. No command edits your shell, global packages, provider profile, MCP settings or CALF preferences.

Prepare `environment.json` outside the pack payload. It contains paths, not credentials:

```json
{
  "python": "/tools/python3",
  "sdk": "/tools/CALF-SDK-0.2.1",
  "calf": "/tools/CALF-Harness-1.8.7/calf",
  "edition": "harness",
  "ffmpeg": "/tools/ffmpeg",
  "ffprobe": "/tools/ffprobe"
}
```

Use resolved physical paths; symlink launcher paths are refused. `sdk` is the directory containing `calf_sdk/`. For Workbench, select its native core executable and `edition: workbench`, not the GUI launcher. No records directory is inferred. Compatibility uses fixed read-only version/capability probes, SDK metadata without import, public core version output and exact qualified core identities from the pack's existing runtime evidence. A version string alone cannot establish compatibility.

On Windows choose short local paths such as `C:\Work\packs` and `C:\Work\media-records`. This preview requires the generated qualification root and the selected native records root to be at most 96 UTF-16 code units, leaving room for retained native snapshots. It refuses longer roots before execution instead of changing the Windows long-path policy. Existing work is not relocated. CJK source/project paths remain supported within the host/tool limits.

## 2. Inspect and stage

Read a reference without starting its tools:

```sh
python3 -B -m calf_extensions.packs.cli inspect --manifest specs/pack-v1/examples/ffmpeg.json
```

For a local trusted-source trial, build a **new candidate**, leaving the shipped 0.1.0 unchanged:

```sh
python3 -B -m calf_extensions.packs.build_ffmpeg --source /work/CALF-Extensions --output /work/new-pack-build --version 0.1.1-dev.2
python3 -B -m calf_extensions.packs.cli --home /work/new-pack-store init
python3 -B -m calf_extensions.packs.cli --home /work/new-pack-store stage --archive /work/new-pack-build/CALF-FFmpeg-Pack-0.1.1-dev.2.zip --sha256 ARCHIVE_SHA256 --source owner-reviewed-local-build
```

`build_ffmpeg` wraps the existing media implementation and public docs with candidate metadata and a complete inventory; it is not a pip distribution or a core/SDK/FFmpeg bundle. Use the printed digest from a trusted build/channel. The source label is provenance supplied by the caller, not a signature or permission grant.

Stage accepts a bounded ZIP or tar archive with files directly at its root. Before activation, it rejects unsafe paths, links, duplicate or case-colliding paths, archives that exceed size limits, inventory mismatches and reference manifests. The copied archive and first error remain in the operation record. The same ID/version cannot be overwritten with different bytes. Repeating the same stage only reads its retained identity; it executes no producer.

## 3. Check, qualify and activate

```sh
python3 -B -m calf_extensions.packs.cli --home /work/new-pack-store check --id calf.media.ffmpeg --version 0.1.1-dev.2 --mode scenes --environment /work/environment.json
python3 -B -m calf_extensions.packs.cli --home /work/new-pack-store qualify --id calf.media.ffmpeg --version 0.1.1-dev.2 --mode scenes --environment /work/environment.json
python3 -B -m calf_extensions.packs.cli --home /work/new-pack-store activate --lock LOCK_ID --expected-active none --experimental
python3 -B -m calf_extensions.packs.cli --home /work/new-pack-store status --id calf.media.ffmpeg
```

`check` does not register or create native work. It reports `COMPATIBLE`, `INCOMPATIBLE` or `UNKNOWN`, observed features and pinned file hashes. `qualify` explicitly executes the existing synthetic media acceptance test in a new records/project folder. It runs the selected candidate with the selected interpreter/SDK, `-I -S -B -X utf8`, then verifies the actual domain report, unchanged payload and dependency hashes. Unicode output is explicit per invocation, including new bound adapters; no locale settings are rewritten. No model/account call is made.

Qualification creates a local immutable lock ID and a receipt for that package/platform/core/dependency set. A pass on another machine or an exit code alone is insufficient. Twelve FFmpeg acceptance groups include the three contract unit tests; the optional second-core comparison is not part of this selected-core installation check. Local qualification is not artistic review or stable-release certification.

Activation requires the lock, current qualified bytes and an exact `expected-active` digest. Use `none` only when no pack is active; otherwise copy `digest` from `status`. This compare-and-swap refuses an intervening selection. Candidate/preview activation also requires `--experimental`. Locks and versions are retained side by side; only the active pointer for future work changes. `status` returns the pointer/digest even when dependency validation fails, with `current: false` and exit 2.

## 4. Bind actual FFmpeg work

Use a new media records directory and a scene project prepared with the existing [FFmpeg guide](FFMPEG.md), outside the pack store. The records directory must exist. Submit one scene against the current active pack:

```sh
python3 -B -m calf_extensions.packs.cli --home /work/new-pack-store scene-request --records /work/media-records --project /work/scenes --scene scene-3 --source /media/scene-3.mp4 --key edit-3-first --profile /work/scene-profile.json
python3 -B -m calf_extensions.packs.cli scene-run --binding /work/new-pack-store/bindings/BINDING_ID/binding.json
python3 -B -m calf_extensions.packs.cli scene-inspect --binding /work/new-pack-store/bindings/BINDING_ID/binding.json
```

The request prints its binding path. It pins the active pack/lock, records/project, copied worker and request data. Those files are also added to the public native adapter registration, so native file-identity checks apply before execution. Registration/submit still use the existing SDK; the manager never writes native journals or SQLite. The scene profile, source and scope use the existing FFmpeg contract.

After actual inspection and authorization, `scene-adopt --binding PATH` uses the existing scene adoption checks. A successful `scene-run` requires current native `verified` **and** `SATISFIED`. Producer exit, handshake and the agent's text do not qualify. The manager never automatically adopts, retries or invokes an agent.

Later run/inspect/adopt calls use the binding's original lock, not the current active pointer. Updates and pack rollback therefore preserve ready work and consumed attempts. All referenced pack, SDK, interpreter, tool, lock and binding files must remain available and unchanged. If a dependency is missing, inspect/reconcile with the documented native API where necessary; do not silently substitute another version.

If submission response is lost, use `scene-reconcile --binding PATH`; it queries the same persisted request without resubmitting. Interrupted registration or unconfirmed native cleanup remains unresolved and requires inspection, not a new request key to hide failure.

## 5. Update, rollback and interrupted activation

Build/stage a new version into a new folder, qualify it, read `status`, then activate its new lock with that digest. Roll back **future selection** using:

```sh
python3 -B -m calf_extensions.packs.cli --home /work/new-pack-store rollback --lock RETAINED_LOCK_ID --expected-active CURRENT_ACTIVE_DIGEST --experimental
python3 -B -m calf_extensions.packs.cli --home /work/new-pack-store recover
python3 -B -m calf_extensions.packs.cli --home /work/new-pack-store recover --acknowledge OPERATION_ID
```

`recover` reads manager transaction intent/result and rechecks identities. It never runs media, edits native records, cancels a native task or frees its reservation. `COMMITTED_UNACKNOWLEDGED` means the active pointer changed but its reply/receipt was lost. `NOT_APPLIED` means the old pointer remains. `RESUMABLE_STAGE` means exact verified staged bytes can finish an interrupted install-metadata write. Explicit acknowledgement completes that local bookkeeping; the first failure/intent is retained.

`UNKNOWN` and `SUPERSEDED_OR_UNKNOWN` are not guessed away. A failed/unfinished runtime qualification remains recorded; no automatic retry. Recovery lists at most 128 operation entries per page and returns `nextCursor`/`pageOnly`; pass `--cursor` to continue. A changed directory generation invalidates the cursor and requires a fresh listing. A page is not an all-history claim.

Old scene restoration remains the separate FFmpeg domain operation. Pack rollback does not change a scene project, select a previous native adoption, restore files, reset attempts or replace settings. This preview deliberately provides no automatic migration, deletion/uninstall or cache eviction that could remove referenced work.

## 6. Verify and understand the boundary

```sh
python3 -B -m calf_extensions.packs.verify --source /work/CALF-Extensions --environment /work/environment.json --output /work/new-pack-lifecycle-test
```

The verifier uses synthetic media, a new store and separate records/projects. It exercises metadata/archive rejection, interrupted staging, selected dependencies, two installed versions, pending-work preservation across update/rollback, real process crashes before/after pointer replacement, CAS and native binding drift. It retains `report.json`, per-install reports and first failures. Existing media tests also check stale evidence, rejected media, scene restoration and scope preservation.

All hashes stream in 32 KiB chunks; discovery imports no SDK/CV module and loads no work/media history. There is one explicit foreground manager and the existing native execution boundary. Owned child execution is bounded. POSIX termination uses a process group; the Windows helper uses bounded termination of its owned process tree with a direct-handle fallback. This is not Windows job-object containment. Normal native adapters retain CALF's own process/job controls. Timeout/uncertain termination must be reconciled before another mutation.

Receipts use file flush/atomic replacement, with directory flush on POSIX. Tests cover process interruption; abrupt power-loss durability is not certified. No memory/soak benchmark, registry signing, malicious same-user filesystem isolation, GUI integration, cloud transport or new provider session is claimed. Extract new tool versions side by side and keep the same explicit store path. Selecting the retained tool folder rolls back the manager without rewriting existing work.
