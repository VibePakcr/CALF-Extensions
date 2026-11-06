# CALF project map development preview

[한국어](REPOSITORY_NAVIGATOR_KR.md) · [Implementation plan](REPOSITORY_LOCAL_GIT_PLAN.md) · [Verification scope](../REPOSITORY_VERIFICATION.json)

A free extension that turns project features, definitions, documents, files and symbols into a relationship map with descriptions, source, Diff and provenance below the map. Local Git supplies exact versions and original content. This extension does not expose Git-operation controls.

This is a source-run development preview. It requires Python 3.10+, Git 2.43+ and a modern browser; the verification summary identifies versions actually tested. Basic execution needs no SDK, CALF core, FFmpeg, account or model API.

## Open a project

From this repository root, run the following. `DATA_DIRECTORY` must be separate from the inspected repository and its Git directories.

```text
python -m calf_extensions.repository.cli open --repo PROJECT_DIRECTORY --data-dir DATA_DIRECTORY
```

The browser opens the project portal. The server listens on an ephemeral `127.0.0.1` port only while the foreground terminal process runs. Stop it with `Ctrl+C`. Add `--no-browser` to open the URL yourself. The installed package entry point is named `calf-repo`.

Collect only tracked files within the explicitly selected project. Do not scan/register an entire PC or GitHub/GitLab account. Refresh is explicit. Source, refs, index, Git configuration and CALF records remain unchanged; captures/cache go to separate app data.

## Link features and terms

Automatically collect structure, document links, Python definitions/docstrings and resolvable static relationships. Do not invent product-feature meaning. Supply a separate UTF-8 JSON with `--project-map CONFIG_FILE` to connect feature/glossary definitions, document evidence and code targets.

```json
{
  "label": "Example project",
  "description": "Prepare and calculate a result.",
  "features": [{
    "id": "execution",
    "label": "Work execution",
    "definition": "Prepare an input and calculate one result.",
    "references": [{"path": "docs/architecture.md", "start_line": 1, "end_line": 3}],
    "targets": [{"path": "app/main.py", "symbol": "run"}]
  }],
  "terms": [{"id": "result", "label": "Result", "definition": "A calculated value."}]
}
```

Paths are project-relative; symbols use file-local `Class.method` or `function` names. Reject duplicate IDs, traversal and invalid line ranges. Missing files, symbols or document ranges remain unresolved. Switching UI language does not translate user definitions, comments, commit messages or code.

## Map and inspector

Use file/symbol views, incoming/outgoing traversal, depths 1/2/3/all analyzed connections, search, zoom/pan/fit and impact candidates. Reverse static reachability describes possible impact, not proven runtime behavior. Distinguish displayed and fully analyzed scope on larger maps.

Selecting a node or edge shows description, linked features, discovery site and line-numbered code below the map. Separate analyzed captures from HEAD, index and current working files, with HEAD-to-selected-version Diff. Conflict index states are not deletions; read stages 1/2/3 independently.

Changed/deleted working files require refresh. Changes during analysis cannot replace the last successful map. Preserve history, pinning, code height, line and camera; reject links to another capture rather than treating versions as equivalent. Provide VS Code URIs and path/line copy. See verification scope for actual editor-launch qualification.

## Capture and offline retention

```text
python -m calf_extensions.repository.cli scan --repo PROJECT_DIRECTORY --data-dir DATA_DIRECTORY --project-map CONFIG_FILE
python -m calf_extensions.repository.cli export --data-dir DATA_DIRECTORY --capture CAPTURE_ID --output NEW_DIRECTORY
python -m calf_extensions.repository.cli export --data-dir DATA_DIRECTORY --capture CAPTURE_ID --output NEW_DIRECTORY --include-source
```

`scan` returns capture identity, scope and entity/relationship counts without opening the portal. `export` uses retained app data, never rereading the original repository. A new output directory contains `START_HERE.html`, `project-navigation.json` and `MANIFEST.json`. Source is excluded by default. `--include-source` embeds retained analyzed source and already cached Diffs; the manifest states inclusion/exclusion coverage.

Static portals open without the repository or server. Offline source viewing is limited to retained analyzed content in this preview. Missing versions/Diffs remain unavailable. Do not automatically include original absolute roots, editor paths, access tokens, Git configuration or CALF records. Including source shares the actual selected project content.

## Qualification and subsequent work

The scoped source tree also passed a macOS wheel build, isolated install, `calf-repo --help`, asset/schema inclusion and SDK-free import check. Windows/Linux wheel installation remains unqualified; existing release archives are unchanged.

The 2026-11-07 synthetic qualification covers macOS Chrome, Windows Edge and Debian Chrome. Debian passed 22 backend checks; Windows passed 21 with one POSIX-only lifecycle fixture skipped. Map-to-inspector, exact call line, Diff, bookmarks, responsive widths and emulated pinch were exercised in actual browsers. Physical phones, native Windows process-tree limits and actual editor launch remain unqualified. See the linked verification summary for retained failure history and exact versions.

The first analyzer uses Python's standard AST. Dynamic calls, ambiguous rebinding and unsupported syntax are never promoted to resolved calls. Rust and JS/TS retain file/document/version navigation with symbol/call analysis explicitly unsupported. Refuse bare/promisor/partial repositories; label shallow boundaries. Do not retrieve LFS payloads or follow submodules/symlink targets automatically.

CALF evidence, GitHub/GitLab APIs, account discovery, additional language analyzers and release qualification are later stages. The index is a navigation projection, not release authority or a successful-check verdict. Existing FFmpeg extension and CALF records are neither moved nor rewritten.
