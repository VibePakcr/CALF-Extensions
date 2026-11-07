# CALF Repository Navigator - free preview

[한국어](NAVIGATOR_PACK_KR.md)

One installed pack provides manual Local Git, GitHub.com and GitLab.com navigation through the same relationship map and below-map description/code/Diff panel. Python 3.10+, Git 2.43+ and a modern browser are required. CALF core, SDK and models are not required.

Extract the trusted bundle into a new folder. Read the included license notices and verify its published SHA256. From that folder:

```text
python START_NAVIGATOR.py install --home STORE --data-dir DATA --preview
python START_NAVIGATOR.py open --home STORE
```

STORE and DATA are separate folders outside inspected repositories. Paths may be supplied relative to the current folder; they are resolved to physical absolute paths. Add `--repo PROJECT` to `install` or `open` to attach one existing Local Git worktree. No repositories or accounts are discovered automatically. Opening without a project shows manual source registration.

Installation checks exact Python/Git identities and runs disposable, offline Local/source/hosted-fixture/portal checks. It retains a qualification lock and activates this preview explicitly. It installs no tools globally and migrates no CALF records. Browser and actual account qualification are separately reported.

Use the source menu to register GitHub/GitLab URLs, choose whether the ref is a branch, tag or full commit ID, enter its name, then start collection. Local working/index versions remain local; remote Diff compares pinned left/right snapshots directly. Partial capture, unavailable text and unknown coverage remain explicit. Source collection is bounded: 1 MiB per file, 64 MiB retained source budget, 300 requests/120 seconds per hosted collection; displayed graph scope is limited to 500 nodes.

For a configured credential reference, start with `open --credential-env MY_TOKEN_NAME`; only the named value travels to the installed worker through a pipe. Enter the same environment variable name in source registration. Never place token values in commands, URLs, screenshots or manuals. Anonymous public access remains subject to provider limits. Private-account behavior is not qualified by the public preview. A shipped gh authentication adapter is not included.

The workspace and captures live outside the immutable installed payload. Each viewer session pins the qualified pack version and owns a workspace lock. Use **Stop viewer** for graceful shutdown, including on Windows; close its browser tab afterward. An interrupted session is not proof of a successful collection.

Use the returned binding with `python START_NAVIGATOR.py run --binding BINDING -- sources list` or other existing `calf-repo` commands. Local root/data/Git/mapping paths are binding-owned and cannot be overridden by forwarded arguments. `inspect --binding BINDING` shows retained session outcomes.

The included illustrated manuals are `manuals/en.html`, `manuals/ko.html` and their PDFs. The installed viewer's User guide link opens the same local documentation. Source/origin inclusion in offline export is explicit and captured originals are never overwritten. Hosted editor actions prepare a separate retained copy. A Local Git editor link opens its selected file path; editing a working file changes that project. Check the version and path before opening an editor. Native editor launch is not qualified.

To update, run the new bundle's `install` with the same store/workspace, `--preview` and the current active digest as `--expected-active`. To select a retained version, use `rollback --home STORE --lock OLD_LOCK --expected-active CURRENT_DIGEST --preview`. Old bindings remain pinned to their original versions, and old packs/captures/receipts remain retained. No automatic migration, uninstall, cache eviction, remote write or background service is added.

