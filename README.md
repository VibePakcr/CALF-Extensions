# CALF Extensions

[한국어](README_KR.md) · [CALF downloads](https://github.com/VibePakcr/CALF/blob/main/DOWNLOADS.md) · [License](LICENSE-EXTENSIONS.txt)

Small, local extensions for **CALF — Controlled Agent Lifecycle Framework**. Connect a runtime to CALF's work contracts, independent checks and version-bound evidence without modifying the proprietary core.

**0.1.0 developer preview:** [Download](https://github.com/VibePakcr/CALF-Extensions/releases/tag/v0.1.0) · [GitLab](https://gitlab.com/vibepackr-group/CALF-Extensions/-/releases/v0.1.0) · [Release notes](RELEASE-NOTES.md). One portable Python package supports the tested macOS, Windows and Linux environments. It is separate from the native CALF installer.

The first extension is a **local FFmpeg scene workflow**, available here as a developer preview. It addresses a common production problem: **change scene 3 while keeping approved scenes 1 and 2 unchanged**.

## What works in this preview

- Render one MP4 candidate for one scene, using installed FFmpeg.
- Check it independently with ffprobe and a complete decode. Check black frames and silence when required by the contract.
- Bind the scene, project version, media hash and validation receipt before adoption.
- Select only the requested scene's validated version. Retain earlier approved files and selection manifests.
- Reject stale evidence, conflicting request keys and adoption against a changed project.
- Restore a retained, validated scene version by selection, without rendering other scenes.

The extension does not call an AI, download tools, start a daemon or load media histories into memory. Media is streamed in 32 KiB chunks for hashing/copying; execution and diagnostics have explicit limits.

## Start here

1. Install [CALF Harness or Workbench](https://github.com/VibePakcr/CALF/blob/main/DOWNLOADS.md) and obtain the separate [CALF SDK 0.2.1](https://github.com/VibePakcr/CALF/releases/tag/sdk-v0.2.1).
2. Install Python 3.10+ and your own FFmpeg/ffprobe with `libx264`, AAC, `blackdetect` and `silencedetect` support. This repository does not bundle them.
3. Follow the [FFmpeg guide](docs/FFMPEG.md). Start with new records and a new scene project before connecting existing work.

The extension uses only Python's standard library and the CALF SDK. The SDK and native runtime are separate dependencies; neither is copied into this repository.

## Agent integration

The work contract is independent of the model. Codex, Antigravity, Claude or another client can use the CLI/SDK from an authorized host. CALF's existing stdio Work MCP can expose recorded evidence to any compatible MCP client. See [agent and MCP integration](docs/AGENTS.md).

**Claude Code 2.1.201 was tested with a real model:** inspect → execute once → inspect, followed by native evidence verification and host-authorized scene selection. The [Claude guide](docs/CLAUDE.md) and [bounded example](examples/claude_work.py) wait for MCP to connect before sending a model request. The scene-selection API, not an agent's completion statement, determines which version is selected.

Approved files are never overwritten by this extension. Read-only file permissions and hashes help protect and detect changes, but they are not an OS sandbox. A separate process with filesystem rights can still modify files outside the controlled path; those rights must be restricted by its host if prevention is required.

## Verified scope

The [verification summary](VERIFICATION.json) records the tools, native cores and scenarios. Short synthetic MP4 tests passed **13 acceptance groups on each of macOS ARM64, Windows 11 x64 and Debian 13 x64**. These groups include three contract unit tests. Harness 1.8.7 and Workbench 1.9.2 native cores read the same records. Tested FFmpeg versions were 8.1.2, 9.0.2 and 7.0.2 respectively.

The live Claude Code workflow was tested on macOS. Claude Desktop GUI configuration, other OS/architecture combinations, production footage, longer jobs, aesthetic/semantic review, ComfyUI, Remotion, Veo, Runway and other generation APIs are **not qualified by these tests**. The reference architecture describes future extensions, not completed integrations.

## Project navigation preview

The working source includes a free [Local Git project navigator](docs/REPOSITORY_NAVIGATOR.md). Select a project to explore features, definitions, documents, files and Python symbols in a relationship map, then inspect descriptions, exact-version code, Diff and provenance below the map.

This source-run development preview is separate from the published FFmpeg 0.1.0 archives. Local Git needs no CALF core, SDK, account or model API. Manually registered GitHub/GitLab sources now share the map and code/Diff inspector; see the [hosted navigation guide](docs/REPOSITORY_HOSTED_H4.md) and [H5 public/desktop qualification and limits](docs/REPOSITORY_HOSTED_H5.md). Private access, native editor launch and physical mobile testing remain unqualified.

## Repository layout

```text
calf_extensions/media_ffmpeg/   runtime, independent validator, scene selection, CLI
docs/                         English/Korean usage and integration guides
examples/                     explicit SDK example
VERIFICATION.json             public verification summary
```

The private CALF engine, user records, contracts, preferences, credentials and generated media are excluded. Existing CALF records are not migrated or rewritten by installing this source.

## Licensing

Use, modification and distribution of these integration sources are allowed for CALF extensions under [LICENSE-EXTENSIONS.txt](LICENSE-EXTENSIONS.txt). The original SDK integration notice is retained in [LICENSE-SDK.txt](LICENSE-SDK.txt). These permissions do not extend to CALF's proprietary core. FFmpeg and other third-party components retain their own licenses.
