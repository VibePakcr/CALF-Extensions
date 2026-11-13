# CALF Extensions

**Start here:** [Installation](INSTALL.md) · [Version and verification map](CURRENT_VERIFICATION.md) · [First-task helper](native-ffmpeg/FIRST_TASK.md)

Preview limits: 64 MiB input/output, 1280×720, 30 seconds, integer 24/25/30 fps and one attempt. These bounds are not a full-resolution production or VFX quality claim.


[한국어](README_KR.md) · [Install](INSTALL.md) · [CALF downloads](https://github.com/VibePakcr/CALF/blob/main/DOWNLOADS.md)

**FFmpeg is the native scene extension.** The optional [CALF Connect IDE frontend](ide-connect/INSTALL.md) is installed separately. Repository Intelligence is now built into CALF Harness 1.8.15 and Workbench 1.9.11. Its module history, exact-record queries and CPU lane/gate connection no longer require a Repository pack.

## FFmpeg scene workflow · 0.2.0-preview.2

Create a new candidate for the scene you want to change, independently check it, then select the verified version. Other approved scenes and previous versions remain intact. A request key prevents an uncertain or repeated request from being blindly submitted again.

The extension is a native **Rust executable**, using the public CALF work protocol. It requires CALF and installed FFmpeg/ffprobe. Python, Node, an SDK runtime, a local model and a background service are not required. The SDK remains available for applications that want a language binding.

- [Install and first use](INSTALL.md)
- [Commands, bounds and recovery](native-ffmpeg/README.md)
- [Current extension catalogue](catalog.json)
- [Latest downloadable release](https://github.com/VibePakcr/CALF-Extensions/releases/tag/ffmpeg-v0.2.0-preview.2)
- [GitLab releases](https://gitlab.com/vibepackr-group/CALF-Extensions/-/releases)

Technical validation checks the frozen media profile and candidate hash, not aesthetic quality. Approval is explicit. No provider account or image/video generation API is called automatically.

## Build from source

```sh
cargo build --release --locked --manifest-path native-ffmpeg/Cargo.toml
cargo test --locked --manifest-path native-ffmpeg/Cargo.toml
```

Use the executable for your OS and architecture. Release verification reports state exactly which platforms and synthetic scenarios were tested; a successful build alone is not runtime qualification.

## Earlier work

Navigator, Video Work Management, motion experiments and earlier Python implementations are excluded from the current catalogue and packages. Their source and published releases remain available as [historical material](legacy/README.md). Existing records, contracts, settings, source media and approved scene versions are not removed or migrated by viewing this repository or installing a new binary.

CALF's proprietary core stays separate. This extension uses its documented interfaces and adds no execution authority. [Extension license](LICENSE-EXTENSIONS.txt).

## Connect your IDE

[CALF Connect](ide-connect/README.md) adds the same four commands to VS Code, Cursor and Antigravity IDE, with a separate PyCharm adapter. [Install](ide-connect/INSTALL.md) · [Actual-screen manual](ide-connect/MANUAL.md). All 12 IDE/OS flows were observed on macOS, Windows and Debian in isolated profiles. This optional development preview is installed separately from FFmpeg and adds no execution or completion authority.


[Earlier releases / 이전 배포](LEGACY.md)
