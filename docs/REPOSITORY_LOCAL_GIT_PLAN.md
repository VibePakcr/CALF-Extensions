# CALF Repository Navigator project map implementation plan

[한국어](REPOSITORY_LOCAL_GIT_PLAN_KR.md) · [Git backend criteria](REPOSITORY_GIT_BACKEND_PLAN.md)

## Product reference

Build a free CALF extension that applies the owner's START_HERE experience to another project: a template and generator that turn project structure into a portal, relationship map and inspector below the entire map. GitHub, GitLab and Local Git supply project/version data.

The main path is **project → features/definitions/documents → modules/files/symbols → incoming/outgoing relationships and impact candidates → code/Diff → verification evidence**. Commit lists and branch graphs are not the primary product. The implemented Git reader supports exact source/version/provenance identities.

A user explicitly registers one project folder. Collect structure, source and document links within that scope and refresh on request. Never scan/register a whole PC/account. Start with Local Git; add GitHub/GitLab PR/MR/CI adapters later.

## First-use experience

1. Open the registered project's start portal, with common navigation for overview, features, documents, source relationships and evidence. Show absent material as unlinked.
2. Select a file/symbol and explore incoming, outgoing and multi-hop relationships with zoom/pan within analyzed scope.
3. Below the entire map, inspect descriptions, definitions, ownership/scope, provenance and linked features.
4. Use exact-version code, line numbers, relationship discovery sites, Diff and editor links in that panel.
5. Restore history, pins, filters, depth and camera; preserve the project map as HTML/JSON.

## P0 Structure and evidence contract

Distinguish `project`, `feature`, `term`, `document`, `module`, `file`, `symbol`, `external_interface`, and `check/evidence`. Give entities IDs, descriptions/definitions, provenance, versions and analysis states. Explicit relations include `CONTAINS`, `DOCUMENTS`, `IMPLEMENTS_FEATURE`, `IMPORTS`, `STATIC_CALL`, `REFERENCES_INTERFACE`, `TEST_REFERENCE` and `SUPPORTED_BY`.

Relation evidence includes file, symbol, line range, commit/blob or captured SHA, discovery method and analyzer version. Static links do not establish execution success or whole-feature coverage. Reverse static reachability produces impact candidates, not proven runtime impacts. Connect native CALF outcomes only through the documented SDK and its exact scope/version.

Feature meaning and glossary definitions come from referenced documentation/comments/user mappings. Do not invent product features from function names. Generate a structure map even without semantic definitions, while marking feature mappings unregistered. Accept explicit feature/term/document/source mappings in project settings outside the repository.

The first analyzer uses Python's standard AST for definitions, imports and resolvable static calls without importing/executing project code. Keep dynamic/ambiguous/unsupported relationships unresolved. Other languages retain file/document/version navigation with explicit symbol/call-analysis limitations. Extend Rust and JS/TS through separate adapters; never present VibePackr's retained GAPE data as analysis of a new repository.

## Implementation sequence

| Phase | Deliverable and exit |
| --- | --- |
| P0 | Freeze project structure schema, relationship provenance, coverage and registration. Eight passing Git fixtures are subordinate evidence, not completion of the map. |
| P1 | Project inventory, document links, feature/glossary mappings and Python AST adapter; match actual files/symbols/lines and resolution states. |
| P2 | Relationship graph, incoming/outgoing traversal, multi-hop and impact candidates; independently verify every resolved edge's provenance and coverage. |
| P3 | Generic START_HERE template/generator, common navigation, map and below-map inspector with definitions/descriptions/code/Diff/editor. |
| P4 | Versioned structure captures, refresh, history/pins/bookmarks and offline HTML/JSON. Git versions remain supporting evidence. |
| P5 | Actual platform/UI/package/preservation and existing FFmpeg regression checks, with aligned EN/KO qualification. |

Live navigation uses a user-opened foreground loopback viewer; retained exports open as static portals without a server. Editor opening is a user action with current-file versus captured-copy identity. Follow the subordinate Git plan for bounded reads, cancellation and external-execution suppression. Do not add Git-operation controls.

## Core acceptance criteria

| ID | Required result |
| --- | --- |
| RN01 | A newly registered project produces a feature/document/source-centered portal without VibePackr paths or captured data |
| RN02 | Independently match Python files, nested symbols, definition lines and docstrings; zero project-code execution |
| RN03 | Exact direction/target/discovery line for resolved imports/static calls; no promotion of dynamic or unsupported references to definitive edges |
| RN04 | Feature/glossary provenance, scope and gaps are visible; no invented definitions or runtime success |
| RN05 | Incoming/outgoing, depths 1/2/3/all analyzed connections, cycles/diamonds/isolated nodes preserve sets and counts; distinguish analysis and display coverage |
| RN06 | Node/edge selection updates below-map description, definition, exact code line and relationship evidence together |
| RN07 | Reverse static reachability is labeled an impact candidate, separate from execution, authority and native CALF success |
| RN08 | HEAD/index/working code, Diff and SHA match; stale files never appear as current captures |
| RN09 | Restore history, pin, filters, line, camera/zoom and same-document hash state with keyboard focus retained |
| RN10 | Offline portal works without original repository; missing source/local paths/credentials/CALF records are never invented or included implicitly |
| RN11 | Actual 1440/390/320px and EN/KO browser checks, independent code scrolling, editor path/line and no console errors |
| RN12 | Preserve refs/index/settings/source and prior FFmpeg/CALF files; no implicit helpers/filters/network; verify limits/cancellation cleanup |

Git LG01–LG28 remain additional reliability/release criteria. Passing Git checks alone does not complete the project-map product. Leave unexecuted platforms, languages and features NOT_RUN/UNSUPPORTED/UNMAPPED and publish only actual qualification. Preserve existing FFmpeg extension and CALF records.

END
