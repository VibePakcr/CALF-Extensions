# Your first managed scene

[한국어](FIRST_TASK_KR.md) · [Install](../INSTALL.md) · [All commands](README.md)

The `first-task` command is included in **0.2.0-preview.2**. Retained 0.2.0-preview.1 downloads use the longer command sequence in the main guide.

You provide the CALF, FFmpeg and ffprobe executable paths, one supported clip, and a new output folder. The helper prepares the tool registration, a two-scene project, a frozen profile and one retained request, then renders and independently checks a candidate. You do not need to create those JSON files or copy identifiers between commands.

Start in Terminal, PowerShell, or the integrated terminal in VS Code, Cursor, PyCharm or Antigravity IDE. Use the executable built for your operating system. Python/Node, a project interpreter, an AI account and an IDE plug-in are not required by this command.

## Check the clip first

Use a deliberately selected, expendable clip with one video stream and at most one audio stream. Limits are **64 MiB source/output, 1280×720, 30 seconds, even dimensions, square pixels and integer 24/25/30 fps**. Known frame count and consistent duration are required; rotated or unsupported metadata is refused. The helper keeps the input dimensions, frame rate and duration, and never silently resizes or trims to fit. H.264/yuv420p and optional stereo 48 kHz AAC are the existing output format.

The existing 100 ms black-frame and silence checks remain enabled (silence only with audio). Intentional fades or silence can therefore fail. Review the profile and use the explicit request workflow when different requirements are intentional; do not weaken checks just to get a green result. Technical validation cannot judge visual appearance.

## Run one command

Replace every example path. The parent of the new output folder must already exist; the output folder itself must not exist.

macOS/Linux:

```sh
'/absolute/calf-ffmpeg' first-task \
  --calf '/absolute/calf' \
  --ffmpeg '/absolute/ffmpeg' --ffprobe '/absolute/ffprobe' \
  --source '/absolute/clip.mp4' --output '/absolute/new-first-task'
```

Windows PowerShell:

```powershell
& 'C:\Tools\calf-ffmpeg.exe' first-task --calf 'C:\Tools\calf.exe' --ffmpeg 'C:\Tools\ffmpeg.exe' --ffprobe 'C:\Tools\ffprobe.exe' --source 'C:\Media\clip.mp4' --output 'C:\Media\new-first-task'
```

The command creates records, configuration and project files **inside that new folder**. Your existing records home and settings are not selected. Neither scene is adopted automatically.

## Review, then choose

Open `NEXT.txt` in the output folder. It contains commands with your actual paths, safely quoted for POSIX shells and PowerShell. Inspect the candidate identified in `first-task-result.json`, play it and review the saved technical checks. `REVIEW_REQUIRED` means technical checks passed and your visual review is still needed; it is not an approved delivery.

Only run the labelled adoption command if you accept that candidate. It invokes the unchanged adoption API, which revalidates the exact bytes. To decline it, simply retain the folder without adopting.

If interrupted or NOT_READY, keep the same folder and use its inspect/reconcile command. `first-task-prepared.json` is saved before rendering. Do not create a new first-task folder as an automatic retry, reset attempts or replace pinned binaries while a retained request references them. Reusing an existing output folder is refused.

The saved measurements cover machine stage times and one entry-command invocation. Human preparation time, human click count and token savings remain unmeasured. No telemetry, provider call or automatic download is performed.
