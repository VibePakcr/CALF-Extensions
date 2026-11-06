# CALF Extensions

[한국어](README_KR.md) · [CALF downloads](https://github.com/VibePakcr/CALF/blob/main/DOWNLOADS.md) · [License](LICENSE-EXTENSIONS.txt)

Small, local extensions for **CALF — Controlled Agent Lifecycle Framework**. Connect a runtime to CALF's work contracts, independent checks and version-bound evidence without modifying the proprietary core.

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

**No live Claude integration is claimed.** The local MCP protocol was tested without calling a model. The scene-selection API, not an agent's completion statement, determines which version is selected.

Approved files are never overwritten by this extension. Read-only file permissions and hashes help protect and detect changes, but they are not an OS sandbox. A separate process with filesystem rights can still modify files outside the controlled path; those rights must be restricted by its host if prevention is required.

## Verified scope

The [verification summary](VERIFICATION.json) records the actual tools, native cores and scenarios. This preview is qualified on **macOS ARM64**, using short synthetic MP4 files. The same records were inspected with Harness 1.8.7 and Workbench 1.9.2 native cores.

Windows and Linux execution of this new extension, production footage, longer jobs, aesthetic/semantic review, ComfyUI, Remotion, Veo, Runway and other external APIs are **not yet qualified**. The reference media architecture is a direction for future extensions, not a list of completed integrations.

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
