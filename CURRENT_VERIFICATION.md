# Which version does a report describe?

**Current native release: FFmpeg 0.2.0-preview.2** includes `first-task`. [Release and exact verification](https://github.com/VibePakcr/CALF-Extensions/releases/tag/ffmpeg-v0.2.0-preview.2). [CALF Connect 0.1.0-dev.1 qualification](ide-connect/QUALIFICATION.json) describes the separate optional IDE frontend.

**현재 배포:** FFmpeg 0.2.0-preview.2에 `first-task`가 포함됩니다. 별도 CALF Connect는 [설치·화면 매뉴얼](ide-connect/INSTALL_KR.md)에서 확인하세요. 아래 preview.1 및 Python 기록은 당시 버전에 관한 역사 근거입니다.

## Retained preview.1 qualification / 이전 검증

[한국어](#한국어) · [Install](INSTALL.md)

| Material | Scope |
| --- | --- |
| Earlier downloadable release | Native Rust FFmpeg 0.2.0-preview.1 |
| Qualified minimum CALF pair for that release | Harness 1.8.15 / Workbench 1.9.11; SDK 0.2.8 was separately tested and is optional |
| First-task in preview.2 | Included in preview.2; absent from retained preview.1 |
| Root VERIFICATION.json, RELEASE-NOTES.md and docs/FFMPEG.md | Historical Python 0.1.0; their earlier evidence is retained |

The retained preview.1 report is the [versioned release asset](https://github.com/VibePakcr/CALF-Extensions/releases/download/ffmpeg-v0.2.0-preview.1/VERIFICATION.json), SHA-256 `17290d45fee36a1c09ff9ba7c8be1c55f2a8f44f6f2696456b3b36a119177bcc` (9,090 bytes). It records the exact three-platform synthetic qualification, not a real-provider or novice-user study. A checksum identifies bytes, not publisher trust.

Installing the native executable does not remove Python/SDK dependencies pinned by earlier jobs. Retain old tools, configurations and binaries while old contracts reference them. Do not reinterpret an older PASS as current validation.

## 한국어

이전 배포는 Rust FFmpeg **0.2.0-preview.1**입니다. 이 릴리즈에서 검증한 최소 CALF 조합은 하네스 **1.8.15**·워크벤치 **1.9.11**이며, 별도 검사한 SDK **0.2.8**은 선택 사항입니다. `first-task`는 preview.2에 포함되며 기존 preview.1 다운로드는 변경하지 않습니다.

최신 릴리즈 검증은 위 버전 고정 자산과 SHA-256으로 확인합니다. 저장소 루트 `VERIFICATION.json`, `RELEASE-NOTES.md`, `docs/FFMPEG.md`는 Python **0.1.0**의 역사 기록입니다. 과거 파일과 PASS를 새 실행의 증거로 바꾸지 않습니다. 네이티브 설치 후에도 옛 계약이 참조하는 Python·SDK·도구·설정·실행 파일은 보관해야 합니다. 검증은 세 운영체제의 합성 실행이며 실제 AI 제공자·초보자 사용성·절감률의 증거가 아닙니다.


## Windows path scope / Windows 경로 범위

Use a short physical pack-store and first-task output path. A final fixture with a 267-UTF-16-unit process working directory was refused by Windows with error 267, including extended path notation. That failed trial remains retained; qualification uses a new shorter user-local folder with the same binaries and checks. Long process working directories are not qualified.

Windows에서는 팩 저장 위치와 첫 작업 결과 폴더를 짧은 실제 경로에 두세요. 프로세스 작업 경로가 UTF-16 267자였던 시험은 Windows 오류 267로 거부됐습니다. 긴 경로 표기도 같은 결과였습니다. 실패 기록은 보존하고 동일 실행 파일·검사 기준으로 짧은 사용자 전용 폴더를 검증합니다. 긴 프로세스 작업 경로는 지원 검증 범위 밖입니다.
