# Connect Claude Code

[한국어](CLAUDE_KR.md) · [Agent/MCP boundaries](AGENTS.md) · [FFmpeg workflow](FFMPEG.md)

Claude is the single requesting agent. FFmpeg rendering, file hashing, validation and scene selection run locally. When you choose a cloud Claude account, it receives the selected task's tool results, including local paths and technical metadata. The example does not upload video files.

The live qualification used **Claude Code 2.1.201 on macOS, with claude-sonnet-5**. It is separate from the three-OS FFmpeg qualification. No Claude Desktop GUI configuration, new model adapter, local model runtime or background service is installed by this extension.

## 1. Prepare one frozen job

Install native CALF Harness 1.8.7 or Workbench 1.9.2, CALF SDK 0.2.1, Python 3.10+ and FFmpeg/ffprobe separately. Follow the FFmpeg guide through `request`, then copy the printed `work` ID. Stop before `run` if Claude will execute this job. Keep its ticket and use the same records home.

Make the SDK importable in the current shell, as described in the FFmpeg guide. The example uses only the standard library and CALF SDK; the separate Claude Agent SDK is not required.

## 2. Select your Claude profile

Use an installed Claude Code CLI and an existing authenticated profile directory. If you want a separate profile, create a new directory and sign in with the official CLI. For example:

```sh
CLAUDE_CONFIG_DIR="/work/claude-profile" claude auth login --claudeai
```

On PowerShell, set `$env:CLAUDE_CONFIG_DIR = 'C:\Work\claude-profile'` for that process, then run `claude auth login --claudeai`. Complete authentication yourself. Do not put tokens into examples, tickets, this repository or a chat. This extension does not copy credentials or rewrite your normal profile.

## 3. Check readiness without a model call

From the extracted extension root, replace every example path and `WORK_ID`:

```sh
python3 -B examples/claude_work.py --claude /tools/claude --calf /tools/calf --home /work/media-records --profile /work/claude-profile --session-dir /work/new-ready-session --work WORK_ID
```

Default mode starts read-only Work MCP, sends the official CLI control `initialize` request, and polls `mcp_status` until `calf` is `connected`. It sends **no user/model message**. `mcpReady: true` is transport readiness, not a new work-verification result.

Always use a new `--session-dir`. For Windows use Windows absolute paths and `python` instead of `python3`. The new helper's model-free path is checked during release qualification; the real Claude model workflow was qualified on macOS only.

## 4. Explicitly execute one job

When you authorize use of your Claude account and one execution, add `--execute` with a new session folder:

```sh
python3 -B examples/claude_work.py --claude /tools/claude --calf /tools/calf --home /work/media-records --profile /work/claude-profile --session-dir /work/new-run-session --work WORK_ID --execute --budget-usd 0.35 --timeout 180
```

This permits `mcp__calf__work_inspect` and `mcp__calf__work_step` only. Built-in shell/file tools are disabled. `dontAsk` denies unapproved actions; it is not permission bypass. The native server is limited to the selected records home. The example requires a ready work at attempt 0 and never submits or retries work automatically.

The CLI receives its USD budget option; account quota/billing follows your Claude plan. The example accepts at most USD 0.50 and 180 seconds. Session persistence, Chrome integration, slash commands and user/project/local settings sources are disabled for this invocation. CLI-owned authentication/cache state may still update in the explicitly selected profile.

After MCP is connected, Claude performs **inspect → step once → inspect**. CALF automatically runs the independent validator after FFmpeg. The host checks current native evidence; the model's text and process exit code cannot establish a pass. The example's exit code is 2 if native evidence is not currently verified and `SATISFIED`.

The helper does not adopt the candidate or update the scene project. Review the result, then use the extension's `adopt` command with the original ticket when authorized. That path rechecks candidate identity, the project version and the other selected scenes.

## Readiness and recovery

A first test sent a prompt while MCP was still `pending`. Claude responded without executing tools; the work remained at attempt 0. The corrected test initialized the control protocol and confirmed `connected` before sending the prompt. It then completed the actual tool sequence and independent validation. The unsuccessful trial was retained.

The helper implements the CLI message shapes published by the official [Claude Agent SDK client](https://github.com/anthropics/claude-agent-sdk-python/blob/main/src/claude_agent_sdk/client.py) and [control query implementation](https://github.com/anthropics/claude-agent-sdk-python/blob/main/src/claude_agent_sdk/_internal/query.py). If a future CLI changes that protocol, readiness fails before the model message. Inspect state and update the integration deliberately; do not treat `pending`, a timeout or a normal CLI exit as success.

After a timeout, reconcile the same native work before any further request. A cancellation request is not proof of termination. Keep the native records and prior candidate; do not erase an attempt to retry. The helper uses process-group cleanup on POSIX and process termination on Windows; forced termination of a Claude process is not a Windows job-tree guarantee. Windows/Linux Claude model execution remains outside this qualification.
