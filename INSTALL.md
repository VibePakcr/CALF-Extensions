# Install the native FFmpeg extension

[한국어](INSTALL_KR.md)

1. Download CALF Harness 1.8.15 or Workbench 1.9.11 from the official CALF release. Keep your existing records home, contracts, settings and older runtimes.
2. Download the FFmpeg extension for your OS/architecture from the current release. Verify its archive SHA-256 and extract into a new folder. Keep earlier versions.
3. Select already installed FFmpeg and ffprobe executables. CALF does not download tools or invoke a model for this setup.
4. Run the packaged `calf-ffmpeg --version`, then follow the [command guide](native-ffmpeg/README.md). Use absolute physical paths. On Windows the executables end in `.exe`.

The core's `calf pack` commands handle staged installation, compatibility checks, independent synthetic qualification, explicit activation and selection of a retained version. `calf pack --help` gives the exact options. A checksum establishes integrity, not publisher identity. Do not activate a package from an untrusted source.

Repository Intelligence is already built in. Do not install the earlier Repository pack on top of it. Other historical extensions are not part of this release.

No original media, records, contracts or unrelated settings need to be copied into the extension folder. Use a new synthetic project for first verification. Technical checks cannot replace your visual review.
