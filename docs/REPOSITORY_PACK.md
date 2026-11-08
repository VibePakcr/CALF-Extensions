# Repository pack: local installation and retained work

[한국어](REPOSITORY_PACK_KR.md) · [Pack manager](PACK_MANAGER.md) · [Project navigator](REPOSITORY_NAVIGATOR.md)

This candidate connects the existing Local Git reader to the common pack manager. It captures HEAD, index and working-file identities and builds a project map with source provenance. It uses Python 3.10+ and Git 2.43+ only. A CALF core, SDK, model account, media tool and background service are not required for this read-only mode.

The managed mode is `inspect`. Hosted GitHub/GitLab access and the live browser viewer have their own guides and qualification; installing this pack does not configure them. The generated offline page is a saved capture, not a live workbench or a proof that the project passed its tests.

## Install in a separate local store

Use physical absolute paths. Commands run from the extracted Local Pack Tools directory, or the CALF Extensions source root. Nothing is installed into a global Python environment. Set up `environment.json` outside the payload:

```json
{"python":"/physical/path/to/python3","git":"/physical/path/to/git"}
```

Use `python` and Windows paths on Windows. Keep the test/store path short; the existing manager refuses qualification roots over its Windows path budget rather than changing OS settings.

Build a new trusted local candidate, or use its supplied ZIP and SHA-256:

```sh
python3 -B -m calf_extensions.packs.build_repository --source /work/CALF-Extensions --output /work/repo-pack-build --version 0.1.0-preview.1
python3 -B -m calf_extensions.packs.cli --home /work/repo-pack-store init
python3 -B -m calf_extensions.packs.cli --home /work/repo-pack-store stage --archive /work/repo-pack-build/CALF-Repository-Pack-0.1.0-preview.1.zip --sha256 TRUSTED_ARCHIVE_SHA256 --source reviewed-local-build
python3 -B -m calf_extensions.packs.cli --home /work/repo-pack-store check --id calf.repository.local-git --version 0.1.0-preview.1 --mode inspect --environment /work/environment.json
python3 -B -m calf_extensions.packs.cli --home /work/repo-pack-store qualify --id calf.repository.local-git --version 0.1.0-preview.1 --mode inspect --environment /work/environment.json
python3 -B -m calf_extensions.packs.cli --home /work/repo-pack-store activate --lock LOCK_FROM_QUALIFY --expected-active none --experimental
```

Check observes exact interpreter/Git identities and supported versions. The fixed driver's declared read policy is separate from behavioral qualification. `qualify` runs three retained test groups against disposable local repositories: Git contracts, navigation contracts and limits. It refuses skipped, missing or failed groups. A compatibility result alone cannot activate a pack. No existing repository, CALF journal or host setting is used for qualification.

## Use the installed version

Choose an existing repository and an existing empty data directory outside it and outside the pack store. The selected data directory holds the retained captures; it is not a CALF records migration.

```sh
python3 -B -m calf_extensions.packs.cli --home /work/repo-pack-store repo-bind --repo /work/my-project --data-dir /work/project-captures
python3 -B -m calf_extensions.packs.cli repo-run --binding /work/repo-pack-store/bindings/BINDING_ID/binding.json
python3 -B -m calf_extensions.packs.cli repo-inspect --binding /work/repo-pack-store/bindings/BINDING_ID/binding.json
python3 -B -m calf_extensions.packs.cli repo-export --binding /work/repo-pack-store/bindings/BINDING_ID/binding.json --output /work/project-map
```

`repo-bind` pins the current qualified pack lock and selected paths. `repo-run` makes one capture with that version. Repeating it returns the existing receipt rather than collecting again. If the process started but no receipt exists, it remains `UNKNOWN`; inspect before taking further action. A new deliberate capture needs a new binding.

The parent verifies the retained capture hash, project-map hash and included source-cache hashes after the worker exits. The source repository is read only: no commit, checkout, fetch, hooks, filters or credentials are invoked by the reader. Exact-version source and coverage limits remain visible. `PARTIAL` is not a complete scan and has a nonzero CLI result. A capture is an observation, not a native CALF `CHECK` receipt for the repository's application tests.

The offline export excludes source text by default. Add `--include-source` only when you intend to copy captured code into that new export. Existing exports are never overwritten. Opening a retained capture does not rescan the original repository.

## Update, select a previous version and reconcile

Build/stage/qualify the next version in a new directory. Read `status`, then activate with its current digest as `--expected-active`. For example:

```sh
python3 -B -m calf_extensions.packs.cli --home /work/repo-pack-store status --id calf.repository.local-git
python3 -B -m calf_extensions.packs.cli --home /work/repo-pack-store activate --lock NEW_LOCK --expected-active CURRENT_DIGEST --experimental
python3 -B -m calf_extensions.packs.cli --home /work/repo-pack-store rollback --lock OLD_LOCK --expected-active NEW_DIGEST --experimental
python3 -B -m calf_extensions.packs.cli --home /work/repo-pack-store recover
```

Both versions, locks, original operation records and captures remain available. Update/rollback changes selection for future bindings. Earlier bindings keep their original pack, dependencies and receipts, even if the active pack changes. Source/dependency drift makes a lock unusable; the manager does not silently substitute a newer executable.

For interrupted installation/activation, `recover` compares retained intent with actual bytes. An explicit `recover --acknowledge OPERATION_ID` finishes confirmed bookkeeping. It does not rerun a scan or rewrite a capture. An uncertain started scan remains an uncertain scan; manager recovery does not manufacture its result. See the manager guide for pagination and process-interruption limits.

No automatic dependency download, registry access, cache eviction, pack deletion, model dispatch or multi-agent runner is added. Hashes stream in bounded chunks. Only the selected capture is loaded. The caller's existing OS/host permissions remain separate from the reader's controlled operations.

## Local CALF history queries

The source preview also provides a separate [history index and module Markdown reader](REPOSITORY_HISTORY.md). It reads an explicitly selected journal and writes disposable views outside the workspace. Current completion still comes from an explicit native query; the original journal is never rewritten. Its qualification and measurements are separate from the Git `inspect` groups above.
