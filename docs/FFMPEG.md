# Local FFmpeg scenes

[한국어](FFMPEG_KR.md) · [Home](../README.md)

This preview makes a new candidate for one scene, checks it, and lets an authorized caller select it. It does not assemble a timeline, generate images/video with AI, or judge artistic quality.

Version 0.1.0 is a portable Python extension for the tested macOS ARM64, Windows 11 x64 and Debian 13 x64 environments. ZIP and tar.gz contain the same source, English/Korean guides and qualification summary. Native CALF, CALF SDK and FFmpeg/ffprobe are installed separately.

Extract updates into a new folder. Keep the complete records home, scene project, old extension/SDK files and tool paths while older work still references them. Contracts pin file identities: replacing or deleting a referenced file can invalidate its current evidence. Register an updated extension in a new configuration folder; do not rewrite old contracts or reset attempts.

## Prepare the environment

Extract CALF SDK 0.2.1 separately. From this repository root, make that extracted SDK importable for the current process. No global shell or CALF settings need changing.

macOS/Linux shell:

```sh
export PYTHONPATH="/absolute/path/to/CALF-SDK-0.2.1"
python3 -B -m calf_extensions.media_ffmpeg.cli --help
```

Windows PowerShell:

```powershell
$env:PYTHONPATH = 'C:\Tools\CALF-SDK-0.2.1'
python -B -m calf_extensions.media_ffmpeg.cli --help
```

Use physical absolute paths to the installed native `calf`/`calf.exe`, FFmpeg and ffprobe. Select the native core, not a GUI launcher. The SDK requires Python 3.10+. FFmpeg must provide libx264, AAC and the detection filters. No tool is downloaded or installed by these commands.

For development, run directly from this source folder. Optional local installation with existing setuptools is `python -m pip install --no-build-isolation --no-deps .`; install the separate SDK into that environment as well. Neither project is published to PyPI by this preview.

## One scene, one candidate

The following commands use example paths; replace all paths with your own. Windows uses the same arguments with Windows absolute paths and `python` in place of `python3`.

```sh
python3 -B -m calf_extensions.media_ffmpeg.cli --calf /tools/calf --home /work/demo-records register --configuration /work/demo-tools --ffmpeg /tools/ffmpeg --ffprobe /tools/ffprobe
python3 -B -m calf_extensions.media_ffmpeg.cli init --project /work/demo-scenes --scenes scene-1 scene-2 scene-3
python3 -B -m calf_extensions.media_ffmpeg.cli --calf /tools/calf --home /work/demo-records request --project /work/demo-scenes --scene scene-3 --source /media/scene-3.mp4 --registration /work/demo-tools/registration.json --key scene3-first --profile /path/to/CALF-Extensions/calf_extensions/media_ffmpeg/profile.json
python3 -B -m calf_extensions.media_ffmpeg.cli --calf /tools/calf --home /work/demo-records run --ticket /work/demo-scenes/requests/scene3-first/ticket.json
```

Registration pins the installed tools, Python executable, imported SDK files and adapter source. Request creation freezes the input and contract without rendering. `run` performs one native step. It returns exit code 2 if the current verdict is not `SATISFIED`; a normal renderer exit alone is insufficient.

After reviewing the candidate and authorizing adoption:

```sh
python3 -B -m calf_extensions.media_ffmpeg.cli --calf /tools/calf --home /work/demo-records adopt --project /work/demo-scenes --ticket /work/demo-scenes/requests/scene3-first/ticket.json
python3 -B -m calf_extensions.media_ffmpeg.cli inspect --project /work/demo-scenes
```

For the initial approved set, repeat request → run → adopt for each scene in sequence. For an edit, use a **new request key**, the target scene ID and its new source. Unselected scenes are not rendered. Reusing a key with the same intent recovers its ticket; different intent is refused. A changed project manifest requires reconciliation or a new deliberate request, never automatic adoption.

## What the technical contract checks

The [sample profile](../calf_extensions/media_ffmpeg/profile.json) requires a one-second 320×180, 25 fps H.264/yuv420p MP4 with stereo AAC at 48 kHz. It rejects black/silent intervals above 100 ms. Adapt the profile to the scene; deliberate fades or silence may be valid for your production.

| Setting | Preview limit / meaning |
|---|---|
| Size | Even dimensions, 16–1280 wide and 16–720 high |
| Frame rate | Integer 24, 25 or 30 fps |
| Clip | 100–30,000 ms; an exact whole number of frames |
| Start | 0–3,600,000 ms from the source |
| Audio | `true`: require AAC stereo 48 kHz; `false`: no audio |
| Black / silence | `null`: not checked; otherwise 100 ms to clip duration |
| Media size | Each input/output ≤64 MiB |
| Scene inventory | 1–32 portable scene IDs |

The producer accepts MP4/MOV-family input with file-only input protocols. Output is MP4. The independent checker verifies stream inventory, dimensions, frame rate, decoded frame count, duration (50 ms tolerance), codecs and a complete error-fatal decode. Detection uses a 100 ms window, black coverage ≥98% at the configured pixel threshold, and silence below −50 dB. These are technical measurements, not content or aesthetic approval.

Encoder/decoder threads are requested at 2, filter threads at 1. This is not an OS-wide CPU quota. Each subprocess has a 25-second deadline and bounded diagnostics; the native operation timeout is 30 seconds. A timeout or unavailable check stays unknown. Nothing automatically submits a new attempt.

## Approval and recovery

`manifest.json` selects a version for each scene. Approved bytes live under `versions/SCENE/VERSION/video.mp4`; previous manifests stay in `manifests/`. The extension never writes new media over an approved version. The retained version record binds the copied bytes to the original CALF contract, manifest and check receipt.

The validator includes the inspected local candidate path/hash in its bounded receipt detail (`calf.media.ffmpeg.validation.v1`). The client reads that public result and hashes the candidate again; it does not infer private CALF storage paths. Before selection, it verifies the native receipt, exact candidate bytes, current project digest and all currently selected scenes. A project lock and compare-and-swap prevent cooperating clients from silently replacing a newer selection.

Use `restore` with a retained version and the **current** digest from `inspect`:

```sh
python3 -B -m calf_extensions.media_ffmpeg.cli restore --project /work/demo-scenes --scene scene-3 --version RETAINED_VERSION_HASH --expected-manifest CURRENT_MANIFEST_HASH
```

This selects a retained verified copy; it does not rerender or rewrite native work history. The copy retains historical validation evidence. A fresh native verdict about a mutable original candidate is a separate fact.

If submit times out, use `reconcile --project /work/demo-scenes --key scene3-first` with `--calf` and `--home`. It uses read-only public list/inspect calls and never resubmits. An unconfirmed result remains unresolved. A stale lock or partial copy is retained for diagnosis rather than automatically deleted or overwritten.

Read-only attributes are a precaution, not immutable storage or an OS sandbox. Out-of-band changes to selected files are detected and block subsequent selection. This preview does not claim atomicity across CALF adoption and project selection, power-loss durability, or protection from a process with unrestricted filesystem access. Reconcile after interrupted operations.

## Run the acceptance test

Use a **new output folder**. The test creates its own short synthetic media and records; it never calls a model or network service.

```sh
python3 -B -m calf_extensions.media_ffmpeg.verify --calf /tools/calf --workbench /tools/workbench-core/calf --ffmpeg /tools/ffmpeg --ffprobe /tools/ffprobe --output /work/new-media-test
```

`--workbench` is optional and selects a second native core for shared-record verification. The test covers three approved scenes, a scene-3-only edit, rejected candidates, stale evidence, restoration, duplicate requests, uncertain-response reconciliation, read-only MCP and out-of-band modification detection. See [VERIFICATION.json](../VERIFICATION.json) for the actual qualification, including untested platforms.
