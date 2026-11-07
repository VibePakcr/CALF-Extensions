# CALF Extensions

**Documentation revision docs.1:** download packages now include the reviewed English and Korean manuals. Runtime code and previous releases are retained. [Changes and verification scope](DOCUMENTATION-RELEASE-20261107.1.md).

Local tools for CALF — Controlled Agent Lifecycle Framework.

[한국어](README_KR.md) · **[Install with an AI assistant](INSTALL.md)** · [CALF core downloads](https://github.com/VibePakcr/CALF/blob/main/DOWNLOADS.md)

## Video Work Management Pack · 0.1.0-preview.1

Keep external video requests, returned files, review, adoption and revisions connected to existing CALF scene records. Returned files retain their original bytes and resolution.

| Start here | Link |
|---|---|
| **1. Download ZIP** | **[GitHub](https://github.com/VibePakcr/CALF-Extensions/releases/download/docs-20261107.1/CALF-Video-Work-Management-Pack-0.1.0-preview.1%2Bdocs.1.zip)** · **[GitLab](https://gitlab.com/-/project/88597295/uploads/91b29c940e075497d7ab5951dfdc43c8/CALF-Video-Work-Management-Pack-0.1.0-preview.1+docs.1.zip)** |
| **2. Install** | **[INSTALL.md — AI-assisted beginner guide](INSTALL.md)** · [한국어](INSTALL_KR.md) |
| **3. Use it** | **[Step-by-step guide with actual captures](docs/media-jobs-manual/README.md)** |
| Other formats / checksums / report | [GitHub](https://github.com/VibePakcr/CALF-Extensions/releases/tag/docs-20261107.1) · [GitLab](https://gitlab.com/vibepackr-group/CALF-Extensions/-/releases/docs-20261107.1) |

Requires Python 3.10+, separate CALF SDK 0.2.1/native executable and FFmpeg/ffprobe. This is an unpack-and-run preview; those dependencies are separate. Qualified on macOS ARM64 with synthetic 1080p clips; Windows/Linux, production footage and provider APIs are not qualified for this added pack.

**Request → external video tool → receive → check → visual review → adopt → revise.** Handoff and download with tools such as Gemini/Veo are manual. Technical checks do not judge aesthetic quality or whether an edit meets the brief.

![Actual macOS Quick Look capture of a synthetic returned MP4](docs/media-jobs-manual/images/finder-returned.jpg)

Actual demo capture; see the guide for all four screens and commands.

## Other downloads

Each feature has its own setup and verification scope.

| Feature | Download | Guide / requirements |
|---|---|---|
| Repository Navigator · 0.1.0-dev.1 | [GitHub](https://github.com/VibePakcr/CALF-Extensions/releases/tag/docs-20261107.1) · [GitLab](https://gitlab.com/vibepackr-group/CALF-Extensions/-/releases/docs-20261107.1) | [Screenshot manual](docs/navigator-manual/README.md). Python and Git; no CALF core/SDK required. |
| Local Pack Tools + Repository Pack · 0.1.0-preview.1 | [GitHub](https://github.com/VibePakcr/CALF-Extensions/releases/tag/docs-20261107.1) · [GitLab](https://gitlab.com/vibepackr-group/CALF-Extensions/-/releases/docs-20261107.1) | [Pack guide](docs/PACKS_GUIDE.md). Python and Git; local read-only repository operations. |
| FFmpeg scene workflow · 0.1.0 | [GitHub](https://github.com/VibePakcr/CALF-Extensions/releases/tag/docs-20261107.1) · [GitLab](https://gitlab.com/vibepackr-group/CALF-Extensions/-/releases/docs-20261107.1) | [FFmpeg guide](docs/FFMPEG.md). Python, SDK/native CALF and FFmpeg/ffprobe. |

The older FFmpeg preview has separate [cross-platform verification](VERIFICATION.json). Its results do not qualify the newer video-management pack. Existing release files and earlier versions remain available.

## Agent and developer references

- [Video CLI, bounds and recovery](calf_extensions/media_jobs/README.md)
- [Existing Work MCP and agent integration](docs/AGENTS.md) · [Claude example](docs/CLAUDE.md)
- [Local pack guide](docs/PACKS_GUIDE.md) · [Preview pack specification](specs/pack-v1/README.md)
- [Extensions license](LICENSE-EXTENSIONS.txt) · [SDK license](LICENSE-SDK.txt)

The SDK/native runtime are separate. Keep old source/tool locations, contracts, records and approved media when preparing a new version in a new folder.

Current guides: [documentation checksums](DOCS-SHA256SUMS). The root `SHA256SUMS` records the original FFmpeg 0.1.0 package; use each release’s checksums for its archives. Published packages retain the manuals supplied with that version.
