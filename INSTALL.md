# Install CALF Extensions

**Open Workbench from an IDE:** [Install CALF Connect](ide-connect/INSTALL.md) · [Illustrated manual](ide-connect/MANUAL.md)

**Manage video candidates:** follow the FFmpeg instructions below. The two downloads are installed separately.

## Install the native FFmpeg extension

The versions in step 1 are the qualified minimum for the current release, not a latest-version claim. [Current vs historical verification](CURRENT_VERIFICATION.md).

Before preparing media, check the preview bounds: 64 MiB source/output, 1280×720, 30 seconds, even dimensions and integer 24/25/30 fps.

FFmpeg 0.2.0-preview.2 includes the [first-task helper](native-ffmpeg/FIRST_TASK.md), reducing setup to one entry command while keeping visual review/adoption explicit. Earlier preview.1 files remain available with their original command sequence. Run it in Terminal/PowerShell or your IDE integrated terminal; no IDE settings need to change.


[한국어](INSTALL_KR.md)

1. Download CALF Harness 1.8.15 or Workbench 1.9.11 from the official CALF release. Keep your existing records home, contracts, settings and older runtimes.
2. Download the FFmpeg extension for your OS/architecture from the current release. Verify its archive SHA-256 and extract into a new folder. Keep earlier versions.
3. Select already installed FFmpeg and ffprobe executables. CALF does not download tools or invoke a model for this setup.
4. Run the packaged `calf-ffmpeg --version`, then follow the [command guide](native-ffmpeg/README.md). Use absolute physical paths. On Windows the executables end in `.exe`.

The core's `calf pack` commands handle staged installation, compatibility checks, independent synthetic qualification, explicit activation and selection of a retained version. `calf pack --help` gives the exact options. A checksum establishes integrity, not publisher identity. Do not activate a package from an untrusted source.

Repository Intelligence is already built in. Do not install the earlier Repository pack on top of it. Other historical extensions are not part of this release.

No original media, records, contracts or unrelated settings need to be copied into the extension folder. Use a new synthetic project for first verification. Technical checks cannot replace your visual review.


## FFmpeg downloads · 0.2.0-preview.2

- [macos arm64](https://github.com/VibePakcr/CALF-Extensions/releases/download/ffmpeg-v0.2.0-preview.2/CALF-FFmpeg-0.2.0-preview.2-macos-arm64.zip)
- [windows x86_64](https://github.com/VibePakcr/CALF-Extensions/releases/download/ffmpeg-v0.2.0-preview.2/CALF-FFmpeg-0.2.0-preview.2-windows-x86_64.zip)
- [linux x86_64](https://github.com/VibePakcr/CALF-Extensions/releases/download/ffmpeg-v0.2.0-preview.2/CALF-FFmpeg-0.2.0-preview.2-linux-x86_64.tar.gz)
