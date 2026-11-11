# Native FFmpeg scene workflow

[한국어](README_KR.md) · [Installation](../INSTALL.md)

Rust implementation of the existing CALF scene workflow. Rendering creates a per-attempt candidate; a separate validator checks its exact bytes against the frozen profile using ffprobe and a full FFmpeg decode. Adoption changes only the selected scene after current native SATISFIED evidence. Source files, earlier candidates and other approved scenes stay intact.

## Commands

Replace example paths with absolute physical paths. On Windows use `calf.exe`, `calf-ffmpeg.exe`, `ffmpeg.exe` and `ffprobe.exe`. A path containing spaces is one quoted argument.

```sh
calf-ffmpeg --version
calf-ffmpeg verify --calf /absolute/calf --ffmpeg /absolute/ffmpeg --ffprobe /absolute/ffprobe --output /absolute/new-test-folder
calf-ffmpeg init --project /absolute/new-project --scenes scene1 scene2
calf-ffmpeg --calf /absolute/calf --home /absolute/records register --configuration /absolute/new-config --ffmpeg /absolute/ffmpeg --ffprobe /absolute/ffprobe
calf-ffmpeg --calf /absolute/calf --home /absolute/records request --project /absolute/new-project --scene scene1 --source /absolute/source.mp4 --registration /absolute/new-config/registration.json --key first --profile /absolute/profile.json
calf-ffmpeg --calf /absolute/calf --home /absolute/records run --ticket /absolute/new-project/requests/first/ticket.json
calf-ffmpeg --calf /absolute/calf --home /absolute/records adopt --project /absolute/new-project --ticket /absolute/new-project/requests/first/ticket.json
calf-ffmpeg inspect --project /absolute/new-project
calf-ffmpeg restore --project /absolute/new-project --scene scene1 --version RETAINED_VERSION_SHA --expected-manifest CURRENT_MANIFEST_SHA
```

Save this example as `profile.json`:

```json
{"width":320,"height":180,"fps":25,"startMs":0,"durationMs":1000,"audio":true,"maxBlackMs":100,"maxSilenceMs":100}
```

## Limits and recovery

One worker, at most one attempt per work, 30 seconds per attempt, 64 MiB per source/output, 1280×720 maximum and 30 seconds of media. Profile fields and rendering arguments are fixed; arbitrary FFmpeg flags are not accepted. CPU rendering uses two threads. Tools and adapter/configuration files are hash-pinned.

Use a new request key for an intentional new candidate. Repeating the same key with the same intent returns the retained ticket; different intent with that key is refused. After a transport failure, use `reconcile --project PROJECT --key KEY` with the same `--calf` and `--home`, then inspect. Do not resubmit an uncertain operation. `restore` selects a retained validated version and checks the current manifest hash; it does not regenerate media or refund incurred costs.

Missing metadata or an uncertain execution remains UNKNOWN. Wrong media specifications remain VIOLATED. Renderer exit 0 is not verification. Technical checks do not judge appearance or editorial meaning; review the candidate before adoption. The extension uses only CALF's public API and cannot constrain direct calls that bypass it.

Old scene/project records keep their v1 schemas. Old candidates and receipts are not rewritten. The native extension is installed separately and does not reinterpret old Python worker receipts as a new execution.
