# H4 common source selection, map and code/Diff

[한국어](REPOSITORY_HOSTED_H4_KR.md) · [Plan](REPOSITORY_HOSTED_PLAN.md) · [Qualification](verification/repository-hosted-h4-20261107.json)

2026-11-07 · Source-run development preview. H4 connects manually registered GitHub/GitLab sources to the existing map and below-map inspector. The Local Git reader, GitHub/GitLab readers, legacy v1 exporter, FFmpeg extension and CALF records remain preserved. This navigation does not grant CALF execution or remote-write authority.

## Open and collect

Start the existing local portal with `open --repo PROJECT_DIRECTORY --data-dir DATA_DIRECTORY` to attach one explicit Local Git worktree. Its source menu also lists manually registered hosted repositories. Alternatively, start directly with a hosted source. Data/output directories must be outside inspected Git repositories.

```text
python -m calf_extensions.repository.cli sources add --provider github --url https://github.com/OWNER/REPO --data-dir DATA_DIRECTORY
python -m calf_extensions.repository.cli sources add --provider gitlab --url https://gitlab.com/GROUP/PROJECT --data-dir DATA_DIRECTORY
python -m calf_extensions.repository.cli scan --source SOURCE_ID --ref-kind branch --ref main --data-dir DATA_DIRECTORY
python -m calf_extensions.repository.cli open --source SOURCE_ID --data-dir DATA_DIRECTORY
```

The UI can register a repository, check its identity, select it, choose a typed branch/tag/full commit and collect explicitly. An optional credential field accepts an **environment variable name**, never a token. H1 authentication and HTTP policies are unchanged. There is no account discovery or automatic clone/fetch/checkout.

`open --source ... --ref-kind branch --ref main` starts an owned collection. `scan --source` requires an explicit typed ref; a partial result exits with code 3. `open --view CONTEXT_ID --data-dir DATA_DIRECTORY` reopens retained content without Git/provider reads. `Ctrl+C` stops the foreground portal and cancels owned workers. A hosted-only portal has no fabricated Local Git source.

## One map and inspector

The active map belongs to the analyzed **right snapshot**. Node/edge selection shows descriptions, explicit feature mappings, source identities and code below the whole map. Code versions are analyzed right, comparison left and comparison right. Changing code versions does not reanalyze or silently change the map. Local Git retains its original HEAD/index/working/conflict-stage behavior.

By default, the comparison left is the selected right commit's first parent. Only verified parentless metadata permits an empty starting state; it is not a fabricated commit. Choose a typed left ref explicitly for another pair. Both refs are pinned before inventory/content collection. The comparison is labeled `DIRECT_SNAPSHOT`; merge-base comparison is not offered.

Changed paths come from the union of pinned inventories, independently of provider patch/compare limits. The list pages through 100 paths. Additions, deletions, modifications, mode changes and unknown inventory scope remain distinct. A unique identical-blob correspondence is only a path hint; it does not rewrite addition/deletion into a proven rename. Deleted files open as comparison-only inspector entries, absent from the current right map. Unfetched/binary/unsupported bytes do not become empty text or a successful empty Diff.

Inventory, retained regular-file bytes, Python analysis, changed paths and text-comparable changes have separate coverage counts. `COMPLETE` collection means complete inventories and regular-file retention, not complete language analysis, text Diff, runtime validation or CALF success. Responses and retained/exported data are bounded; large Diff output can remain `PARTIAL` with identity preserved.

## Selection, history and cancellation

Collection runs in an owned job while the previous map stays usable. Progress reports phase, requests, file count and retained content. Cancel or a newer source selection prevents the old job from publishing. A failed collection keeps the previous active map. A partial capture is retained but must be opened explicitly from retained maps; it never automatically replaces a successful map.

Retained v2 snapshots/views are create-only under separate app data. History keeps context, snapshot, navigation, ref and comparison identities; a same-source update records its predecessor. Cached source selection needs no network. Disabling registration keeps existing retained maps and refuses new collection. Cancellation may leave unindexed immutable snapshot/cache inputs written before the publication check; it cannot make them an active map.

Exploration links bind source, context, capture, navigation and comparison snapshots, together with selection, line, pin, camera, code height and language. Different identities are refused. Context checks and browser request generations prevent delayed old code/Diff responses from replacing another selected source.

## Provider links and editor copies

Provider file links use the verified repository URL and pinned commit. Hosted sources expose no local working/index/stage controls. “Prepare retained code copy” writes a separate, hash-checked, safe-named editor copy under app data and then offers a VS Code URI. Editing that copy changes neither captured bytes nor the provider. Native editor launch was not qualified in H4; no editor is launched automatically. Existing Local Git editor links remain unchanged.

## Offline v2 export

```text
python -m calf_extensions.repository.cli export --data-dir DATA_DIRECTORY --view CONTEXT_ID --output NEW_OUTPUT_DIRECTORY
python -m calf_extensions.repository.cli export --data-dir DATA_DIRECTORY --view CONTEXT_ID --output NEW_OUTPUT_DIRECTORY --include-source
```

Source and original bytes are opt-in with `--include-source`. Origin URL/repository identity/ref names require the separate `--include-origin` option. By default the projection uses an opaque source identity and commit IDs, excludes editor/local paths and credential references, and offers no editor action. Project content, filenames, descriptions and user definitions remain map content; export does not automatically scrub secrets embedded in that content. Inspect content before sharing.

Included original bytes retain Base64 and SHA256 evidence. Included code/Diff works from retained data with the original repository hidden and HTTP blocked. Manifest coverage distinguishes retained completeness from the bounded exported subset; omitted source is unavailable. Output must be new and outside repository/app-data directories. Legacy `--capture` export remains unchanged.

## Qualification and remaining scope

Fresh macOS evidence covers 121 repository tests, 20 focused H4 checks after final version-guard refinement, three FFmpeg contract checks, real Chrome hosted-fixture/live-portal and offline rendering, plus independent frozen Local Git/v1 browser regression. The hosted browser uses unchanged GitHub/GitLab readers over independently generated real Git objects and provider-shaped responses; it is **not a fresh live-provider or private-account qualification**. Prior H2/H3 public-reader evidence stays historical and unchanged.

Chrome checks cover below-map code/Diff, call line 6, pinned provider links, editor-copy URI, ref-side versions, delayed response isolation, bookmark/language/height restoration, escaped script canary and 1440/390/320 widths. Offline checks hide originals and block HTTP. Owned server sockets/workers/browser processes are closed after qualification.

H5 remains pending: private-provider permissions, full live-provider matrix, Windows/Linux hosted UI, physical mobile devices, native editor launch, fresh package installation and performance/peak-memory measurements. HG01–HG32 remain NOT_RUN for the full matrix; scoped H4 progress is recorded separately. No commit/push or package publication is included.

