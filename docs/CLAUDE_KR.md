# Claude Code 연결

[English](CLAUDE.md) · [에이전트·MCP 경계](AGENTS_KR.md) · [FFmpeg 작업 흐름](FFMPEG_KR.md)

Claude는 작업을 요청하는 단일 에이전트입니다. FFmpeg 렌더링·파일 해시·검수·씬 선택은 로컬에서 수행합니다. 클라우드 Claude 계정을 연결하면 선택한 작업의 도구 응답에 담긴 로컬 경로·기술 메타데이터가 Claude에 전달됩니다. 예제는 영상 파일을 업로드하지 않습니다.

실제 작업은 **macOS의 Claude Code 2.1.201·claude-sonnet-5**로 검증했습니다. FFmpeg 확장의 세 OS 검증과는 구분합니다. 이 확장이 Claude Desktop GUI 설정, 새 모델 어댑터, 로컬 모델이나 상주 서비스를 설치하지는 않습니다.

## 1. 실행 전 작업 준비

네이티브 CALF Harness 1.8.7 또는 Workbench 1.9.2, CALF SDK 0.2.1, Python 3.10 이상, FFmpeg/ffprobe를 별도로 준비합니다. FFmpeg 안내의 `request`까지 진행하고 출력된 `work` ID를 확인합니다. Claude가 실행할 작업이라면 아직 `run`은 하지 마세요. 원래 티켓과 같은 기록 폴더를 사용합니다.

현재 셸에서 SDK를 읽을 수 있도록 FFmpeg 안내의 경로 설정을 적용합니다. 예제는 표준 라이브러리와 CALF SDK만 사용하며 별도 Claude Agent SDK 설치는 필요하지 않습니다.

## 2. Claude 프로필 선택

설치된 Claude Code CLI와 로그인된 프로필 디렉터리를 지정합니다. 별도 프로필을 원하면 새 디렉터리를 만들고 공식 CLI로 로그인할 수 있습니다.

```sh
CLAUDE_CONFIG_DIR="/work/claude-profile" claude auth login --claudeai
```

PowerShell은 현재 프로세스에 `$env:CLAUDE_CONFIG_DIR = 'C:\Work\claude-profile'`을 지정한 뒤 `claude auth login --claudeai`를 실행합니다. 인증은 직접 완료하세요. 토큰을 예제·티켓·저장소·채팅에 넣지 마세요. 확장이 인증정보를 복사하거나 평소 프로필을 다시 쓰지는 않습니다.

## 3. 모델 호출 없이 연결 확인

압축을 푼 확장 루트에서 실행합니다. 모든 예시 경로와 `WORK_ID`를 실제 값으로 바꾸세요.

```sh
python3 -B examples/claude_work.py --claude /tools/claude --calf /tools/calf --home /work/media-records --profile /work/claude-profile --session-dir /work/new-ready-session --work WORK_ID
```

기본 모드는 읽기 전용 Work MCP를 시작하고 공식 CLI 제어 규약의 `initialize`를 보낸 뒤, `mcp_status`에서 `calf`가 `connected`인지 확인합니다. **사용자 메시지를 보내거나 모델을 호출하지 않습니다.** `mcpReady: true`는 연결 준비 완료이며 새로운 작업 검수 통과를 뜻하지 않습니다.

`--session-dir`는 매번 새 폴더를 지정하세요. Windows에서는 Windows 절대 경로와 `python` 명령을 사용합니다. 새 예제의 모델 미호출 경로는 릴리즈 검수에서 확인하며, 실제 Claude 모델 작업은 macOS에서만 검증했습니다.

## 4. 승인한 작업 한 번 실행

Claude 계정 사용과 작업 1회 실행을 허용할 때는 새 세션 폴더와 `--execute`를 지정합니다.

```sh
python3 -B examples/claude_work.py --claude /tools/claude --calf /tools/calf --home /work/media-records --profile /work/claude-profile --session-dir /work/new-run-session --work WORK_ID --execute --budget-usd 0.35 --timeout 180
```

허용 도구는 `mcp__calf__work_inspect`와 `mcp__calf__work_step`뿐입니다. 내장 셸·파일 도구는 비활성화합니다. `dontAsk`는 허용하지 않은 동작을 거절하며 권한 우회 모드가 아닙니다. 네이티브 서버는 지정한 기록 폴더를 사용합니다. 예제는 아직 실행하지 않은 준비 상태·시도 수 0인 작업만 실행하며 자동 제출·재시도하지 않습니다.

예산 인수는 Claude CLI에 전달하며 계정의 사용량·과금 조건은 해당 Claude 요금제를 따릅니다. 예제의 최대 설정은 US$0.50·180초입니다. 이번 호출에서는 세션 저장·Chrome 연결·슬래시 명령과 사용자·프로젝트·로컬 설정 소스를 비활성화합니다. 지정한 프로필의 인증·캐시 상태는 CLI 동작에 따라 갱신될 수 있습니다.

MCP 연결이 완료되면 Claude가 **조회 → 1회 실행 → 재조회**를 수행합니다. FFmpeg 실행 뒤 CALF가 독립 검사기를 자동으로 실행합니다. 호스트는 현재 네이티브 증거를 확인하며, 모델의 답변이나 프로세스 종료 코드만으로 통과시키지 않습니다. 네이티브 증거가 현재 유효하고 `SATISFIED`인 경우가 아니면 예제는 종료 코드 2를 반환합니다.

이 예제는 후보 채택이나 씬 프로젝트의 선택 목록을 변경하지 않습니다. 결과 확인 후 권한이 있다면 원래 티켓으로 확장의 `adopt`를 실행하세요. 후보의 동일성·프로젝트 버전·다른 선택 씬을 다시 확인합니다.

## 연결 준비와 복구

첫 시험에서는 MCP가 `pending`일 때 프롬프트가 먼저 전송됐습니다. Claude는 도구 실행 없이 응답했고 작업은 시도 수 0에 머물렀습니다. 제어 규약으로 초기화하고 `connected`를 확인한 뒤에만 프롬프트를 보내도록 수정하자 실제 도구 실행과 독립 검수를 완료했습니다. 실패한 첫 시험 기록도 보존했습니다.

예제는 공식 [Claude Agent SDK 클라이언트](https://github.com/anthropics/claude-agent-sdk-python/blob/main/src/claude_agent_sdk/client.py)와 [제어 규약 구현](https://github.com/anthropics/claude-agent-sdk-python/blob/main/src/claude_agent_sdk/_internal/query.py)에 공개된 CLI 메시지 형식을 사용합니다. 향후 CLI 규약이 바뀌면 모델 메시지 전송 전에 연결 확인이 실패합니다. 현재 상태를 확인하고 연동을 갱신하세요. `pending`·시간 초과·정상 종료만으로 작업을 성공 처리하면 안 됩니다.

시간 초과 뒤에는 같은 네이티브 작업부터 확인하세요. 취소 요청은 종료 완료 증거가 아닙니다. 기록과 이전 후보를 남겨두고 시도를 지워서 재시도하지 마세요. 예제는 POSIX에서 프로세스 그룹 정리를, Windows에서는 프로세스 종료를 사용합니다. Claude 프로세스 강제 종료가 Windows 하위 작업 전체의 종료까지 보장하지는 않습니다. Windows·Linux의 Claude 모델 실행은 이번 검증 범위에 포함되지 않습니다.
