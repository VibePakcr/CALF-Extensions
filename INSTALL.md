# Install with an AI assistant

[한국어](INSTALL_KR.md) · [README](README.md) · [Illustrated video-work guide](docs/media-jobs-manual/README.md)

This guide helps first-time users prepare CALF Extensions with an AI assistant. It focuses on the **Video Work Management Pack 0.1.0-preview.1**. Setup does not require an AI model or generation API key. Your external tool generates the video; CALF manages handoffs, returns, checks, adoption and revision records.

## Download first

**[Download ZIP · GitHub](https://github.com/VibePakcr/CALF-Extensions/releases/download/media-jobs-v0.1.0-preview.1/CALF-Video-Work-Management-Pack-0.1.0-preview.1.zip)** · [Download ZIP · GitLab](https://gitlab.com/vibepackr-group/CALF-Extensions/-/releases/media-jobs-v0.1.0-preview.1/downloads/CALF-Video-Work-Management-Pack-0.1.0-preview.1.zip)

Extract 0.1.0-preview.1 into a **new folder**, then open its `INSTALL.md`. Enable “show file extensions” in your file manager if needed. This is separate from the older FFmpeg 0.1.0 archive. Extracting it does not replace existing CALF or activate a pack.

Other formats, SHA256SUMS and verification report: [GitHub](https://github.com/VibePakcr/CALF-Extensions/releases/tag/media-jobs-v0.1.0-preview.1) · [GitLab](https://gitlab.com/vibepackr-group/CALF-Extensions/-/releases/media-jobs-v0.1.0-preview.1)

## 1. Give your AI assistant this request

Open the CALF Extensions folder in an AI tool that can read local files and run commands, then paste this request. With a chat-only assistant, use the same request to obtain instructions and run the commands yourself.

```text
Read INSTALL.md, AGENTS.md and README.md in this folder, and help me set up the CALF Extensions Video Work Management Pack 0.1.0-preview.1 for the first time.
Check my operating system and actual file locations. Look for an existing Python 3.10+, CALF SDK, native calf executable, and FFmpeg/ffprobe first.
Check that calf_extensions/media_jobs/cli.py exists. If it is missing, explain which source distribution I need; do not invent missing files or claim installation succeeded.
Reuse existing tools. If installing software or changing global settings is necessary, explain the changes and ask for my confirmation.
Preserve existing projects, settings, records and approved videos. Run the first verification in a separate new folder.
Do not include AI API-key setup, paid generation calls or adoption of candidates in my existing projects in this installation.
Verify completion with actual commands and results. Give me the selected paths, first-run command and verification-result location, and distinguish anything you could not execute.
```

## 2. Choose the right feature and files

| Goal | What you need / guide |
|---|---|
| Manage AI video handoffs, returns and revisions | This `media_jobs` pack, Python, separate CALF SDK/native executable, FFmpeg/ffprobe |
| Produce local FFmpeg scene candidates | [Existing FFmpeg extension guide](docs/FFMPEG.md) |
| Explore source repositories | Separate Repository Navigator download and [README installation steps](docs/navigator-manual/README.md). This mode does not require CALF core/SDK. |
| Install/update local Repository packs | [Common pack guide](docs/PACKS_GUIDE.md) |

This distribution includes the files below. Retain its README, INSTALL, source and image directories together. With Python available, run `python3 -B VERIFY_PACKAGE.py` from the extracted folder to check payload hashes first. This needs no SDK/CALF and does not establish a native work verdict. For a repository checkout, consult the release checksums and report instead of that archive-only file.

```text
CALF-Video-Work-Management-Pack-0.1.0-preview.1/
  INSTALL.md
  calf_extensions/
    media_jobs/
      cli.py
      verify.py
```

Official sources: [CALF native executable](https://github.com/VibePakcr/CALF/blob/main/DOWNLOADS.md) · [CALF SDK 0.2.1](https://github.com/VibePakcr/CALF/releases/tag/sdk-v0.2.1) · [Python](https://www.python.org/downloads/) · [FFmpeg](https://ffmpeg.org/download.html)

## 3. Locate these five items with your assistant

| Item | Select |
|---|---|
| CALF Extensions | The folder containing this document and `calf_extensions` |
| Python | `python3` version 3.10+; usually `python` on Windows |
| SDK | The folder directly containing `calf_sdk` |
| Native executable | The actual `calf` file, or `calf.exe` on Windows; not a GUI launcher |
| Media tools | The actual `ffmpeg` and `ffprobe` files; `.exe` on Windows |

The recommended setup runs **directly from the source folder**. It needs no `pip install` or global shell/MCP configuration changes. Paths below are examples: ask your assistant to substitute actual paths. Keep the quotes around paths containing spaces.

## 4. Confirm that help opens first

macOS/Linux shell example. Actual execution of this management addition was verified on macOS.

```sh
cd "/absolute/path/to/CALF-Extensions"
export SDK="/absolute/path/to/CALF-SDK-0.2.1"
export NATIVE="/absolute/path/to/calf"
export FFMPEG="/absolute/path/to/ffmpeg"
export FFPROBE="/absolute/path/to/ffprobe"
export PYTHONPATH="$PWD:$SDK"
python3 --version
python3 -B -c 'import calf_sdk; print(calf_sdk.__file__)'
"$NATIVE" --version
python3 -B -m calf_extensions.media_jobs.cli --help
```

If help lists `register`, `request`, `receive`, `run`, `adopt`, `reconcile` and `status`, you have found the entrypoint. This has not executed a video task or contacted a generation service. These environment variables apply to the current terminal session.

Windows PowerShell uses the following equivalent path/help syntax. This example does not qualify the added management workflow on Windows.

```powershell
Set-Location 'C:\Work\CALF-Extensions'
$SDK = 'C:\Tools\CALF-SDK-0.2.1'
$NATIVE = 'C:\Tools\CALF\calf.exe'
$FFMPEG = 'C:\Tools\ffmpeg\bin\ffmpeg.exe'
$FFPROBE = 'C:\Tools\ffmpeg\bin\ffprobe.exe'
$env:PYTHONPATH = "$((Get-Location).Path);$SDK"
python --version
python -B -c "import calf_sdk; print(calf_sdk.__file__)"
& $NATIVE --version
python -B -m calf_extensions.media_jobs.cli --help
```

## 5. Run a short demo before using your own footage

This command generates short synthetic clips with FFmpeg and checks handoff, intake, verification, adoption and restoration in separate records and a separate scene project. It makes no model or generation API calls. Choose a **new output directory that does not exist yet**.

macOS/Linux:

```sh
export CHECK="/absolute/path/to/new-media-install-check"
python3 -B -m calf_extensions.media_jobs.verify --calf "$NATIVE" --ffmpeg "$FFMPEG" --ffprobe "$FFPROBE" --output "$CHECK"
```

Equivalent Windows PowerShell command syntax:

```powershell
$CHECK = 'C:\Work\new-media-install-check'
python -B -m calf_extensions.media_jobs.verify --calf $NATIVE --ffmpeg $FFMPEG --ffprobe $FFPROBE --output $CHECK
```

On success, `verification.json` in the output directory records `"status": "PASS"`. Opening help and passing the full verification are different milestones. On failure, retain the output folder and ask your assistant to inspect the actual error/results. Do not delete records or lower requirements to obtain a pass.

## 6. Start managing your video work

Follow the [illustrated user guide](docs/media-jobs-manual/README.md).

1. Create a `request` from your edit instructions and references.
2. Pass its `handoff.txt` and reference snapshots to your video tool.
3. Download the result, `receive` it, then `run` its checks.
4. Review the original and returned footage before using `adopt` for a chosen version.

Handoff/download with Gemini/Veo or another external tool is currently manual. CALF's technical verdict does not establish aesthetic quality or satisfaction of the requested edit.

## What to show your assistant if you get stuck

| Message or situation | Check |
|---|---|
| `No module named calf_extensions` | Current terminal directory is the source root; the folder includes `media_jobs` |
| `No module named calf_sdk` | `SDK` is the parent of `calf_sdk`; current-session `PYTHONPATH` is correct |
| Native executable not found | `NATIVE` is the actual absolute path to `calf`/`calf.exe` |
| FFmpeg/ffprobe execution or checks fail | Executable paths, codec/filter support and the actual error output |
| An error requires a new folder | Choose a fresh path; retain existing settings/results |
| `VIOLATED` or `UNKNOWN` | Inspect the actual result and requirements; do not report it as a pass or successful setup |

Share the OS, command, error message and result location with your assistant. This installation does not need passwords or API keys.

## Updates and retention

Prepare a new version in a separate folder and register it with a new tool configuration. Replacing/removing source, SDK or tool files pinned by older contracts can invalidate existing evidence. Keep the earlier records home, scene project, approved media and their referenced source/tool locations together. See the [video-management guide](calf_extensions/media_jobs/README.md) for recovery details.
