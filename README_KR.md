# CALF Extensions

[English](README.md) · [CALF 다운로드](https://github.com/VibePakcr/CALF/blob/main/DOWNLOADS.md) · [라이선스](LICENSE-EXTENSIONS.txt)

**CALF — Controlled Agent Lifecycle Framework**에 연결하는 작은 로컬 확장 모음입니다. 비공개 코어를 수정하지 않고 런타임을 작업 계약·독립 검사·파일 버전이 연결된 실행 증거와 결합합니다.

**0.1.0 개발자 프리뷰:** [다운로드](https://github.com/VibePakcr/CALF-Extensions/releases/tag/v0.1.0) · [GitLab](https://gitlab.com/vibepackr-group/CALF-Extensions/-/releases/ffmpeg-v0.1.0) · [릴리즈 안내](RELEASE-NOTES.md). 하나의 Python 공용 패키지로 검증된 macOS·Windows·Linux 환경에서 사용합니다. CALF 앱 설치 파일과는 별도입니다.

첫 확장은 **로컬 FFmpeg 씬 작업 흐름**이며, 개발자 프리뷰로 제공합니다. **승인된 1·2번 씬은 그대로 두고 3번 씬만 수정하는 것**이 이번 구현의 핵심입니다.

## 이번 프리뷰에서 가능한 것

- 지정한 씬 하나의 새 MP4 후보를 설치된 FFmpeg로 만듭니다.
- ffprobe와 전체 디코딩으로 독립 검사합니다. 계약에서 요구하면 검은 화면과 무음 구간도 확인합니다.
- 씬·프로젝트 버전·미디어 해시·검사 영수증을 확인한 뒤 채택합니다.
- 요청한 씬의 검증된 버전만 선택합니다. 이전 승인 파일과 선택 이력은 남겨둡니다.
- 검사 후 바뀐 파일, 같은 요청 키의 다른 내용, 프로젝트 변경 이후의 오래된 채택 요청을 거절합니다.
- 이전 검증본을 다시 선택해 복원합니다. 다른 씬을 다시 렌더링하지 않습니다.

AI 호출·도구 다운로드·상주 서비스를 추가하지 않습니다. 미디어 이력 전체를 메모리에 올리지 않으며, 해시와 파일 복사에는 32 KiB 단위 스트리밍을 사용합니다. 실행 시간과 진단 출력에도 한도가 있습니다.

## 시작하기

1. [CALF Harness 또는 Workbench](https://github.com/VibePakcr/CALF/blob/main/DOWNLOADS.md)를 설치하고 별도 [CALF SDK 0.2.1](https://github.com/VibePakcr/CALF/releases/tag/sdk-v0.2.1)을 받습니다.
2. Python 3.10 이상과 FFmpeg/ffprobe를 준비합니다. FFmpeg에는 `libx264`·AAC·`blackdetect`·`silencedetect`가 필요합니다. 이 저장소에는 도구를 동봉하지 않습니다.
3. [FFmpeg 사용 안내](docs/FFMPEG_KR.md)를 따라 새 기록 폴더와 새 씬 프로젝트에서 먼저 시험합니다.

Python 표준 라이브러리와 CALF SDK만 사용합니다. SDK와 네이티브 런타임은 별도로 준비하며, 이 저장소에 복제하지 않습니다.

## AI 에이전트 연결

작업 계약은 모델에 종속되지 않습니다. Codex·Antigravity·Claude 등은 권한을 부여받은 호스트에서 CLI/SDK를 사용할 수 있습니다. CALF의 기존 stdio Work MCP로 호환 클라이언트에 실행 증거를 제공할 수도 있습니다. [에이전트·MCP 연결 안내](docs/AGENTS_KR.md)를 참고하세요.

**Claude Code 2.1.201은 실제 모델로 조회 → 1회 실행 → 재조회를 수행했습니다.** 이후 네이티브 증거를 확인하고 호스트가 승인한 씬 선택까지 검증했습니다. [Claude 연결 안내](docs/CLAUDE_KR.md)와 [실행 한도가 있는 예제](examples/claude_work.py)는 MCP 연결이 완료된 뒤에만 모델에 작업을 전달합니다. 어떤 버전을 선택할지는 AI의 완료 선언이 아니라 씬 선택 API가 결정합니다.

이 확장은 승인 파일을 덮어쓰지 않습니다. 읽기 전용 파일 속성과 해시로 변경을 보호·감지하지만 OS 샌드박스는 아닙니다. 별도 프로세스에 파일 쓰기 권한이 있으면 통제 경로 밖에서 변경할 수 있으므로, 이를 차단하려면 해당 호스트에서 권한을 제한해야 합니다.

## 실제 검증 범위

[검증 요약](VERIFICATION.json)에 도구·네이티브 코어·시험 항목을 기록했습니다. 짧은 합성 MP4로 **macOS ARM64·Windows 11 x64·Debian 13 x64에서 각각 13개 수락 항목**을 통과했습니다. 이 항목에는 계약 단위 검사 3개가 포함됩니다. Harness 1.8.7과 Workbench 1.9.2의 네이티브 코어가 같은 기록을 확인했습니다. FFmpeg는 순서대로 8.1.2·9.0.2·7.0.2를 사용했습니다.

Claude Code 실제 작업은 macOS에서 확인했습니다. Claude Desktop GUI 설정, 다른 OS·아키텍처 조합, 실제 제작 영상, 장시간 작업, 미적·의미적 검수, ComfyUI·Remotion·Veo·Runway 등 생성 API는 **이번 시험의 검증 범위가 아닙니다**. 미디어 참조 아키텍처는 후속 확장의 방향이며, 완료된 연동 목록이 아닙니다.

## 프로젝트 탐색 미리보기

**무료 설치형 Repository Navigator 프리뷰:** [ZIP·체크섬·한영 매뉴얼 다운로드](https://github.com/VibePakcr/CALF-Extensions/releases/tag/navigator-v0.1.0-dev.1). Local Git과 수동 등록한 GitHub·GitLab을 같은 지도·코드·Diff로 탐색합니다. Python·Git만 필요하며 CALF core·SDK·모델은 요구하지 않습니다.

작업 소스에는 무료 [Local Git 프로젝트 탐색기](docs/REPOSITORY_NAVIGATOR_KR.md)가 포함됩니다. 프로젝트를 선택하면 기능·정의·문서·파일·Python 심볼의 관계 지도를 탐색하고, 맵 아래에서 설명·정확한 버전의 코드·Diff·출처를 확인할 수 있습니다.

현재는 소스에서 실행하는 개발 미리보기이며 공개된 FFmpeg 0.1.0 압축파일과는 별도입니다. Local Git는 CALF 코어·SDK·계정·모델 API를 요구하지 않습니다. 수동 등록한 GitHub·GitLab 소스도 같은 지도와 코드/Diff 패널로 탐색합니다. [원격 탐색 안내](docs/REPOSITORY_HOSTED_H4_KR.md)와 [H5 공개·데스크톱 검증 범위](docs/REPOSITORY_HOSTED_H5_KR.md)를 확인하십시오. 비공개 접근·에디터 실행·실제 모바일 검증은 남아 있습니다.

Local Git·GitHub·GitLab을 묶은 [설치형 Repository Navigator 프리뷰](docs/NAVIGATOR_PACK_KR.md)와 실제 화면이 담긴 [한글](docs/navigator-manual/ko.html)·[영문](docs/navigator-manual/en.html) 매뉴얼을 추가했습니다. 세 운영체제 설치 검사와 범위는 [설치본 검증](docs/NAVIGATOR_PACK_VERIFICATION.json)에 기록합니다.

## 저장소 구성

작업 소스에는 [로컬 팩 설치·업데이트 프리뷰](docs/PACK_MANAGER_KR.md)와 [공통 팩 규격](docs/EXTENSION_PACK_SPEC_KR.md)도 있습니다. 후보 팩을 준비·검수하고 의존성 잠금 정보를 보존하며 업데이트·버전 복귀 뒤에도 기존 작업을 이어갑니다. [Repository 로컬 Git inspect](docs/REPOSITORY_PACK_KR.md)는 Python·Git만 사용하는 별도 설치·검수 경로와 버전이 고정된 작업 바인딩을 지원합니다. 이 개발 기능은 **공개된 0.1.0 압축파일에는 포함되지 않았습니다.** 등록소 다운로드·필수 모델·상주 서비스를 추가하지 않으며, 모션은 이 팩 생명주기 프리뷰에서 아직 구현하지 않았으며, 별도 Repository Navigator가 관리형 foreground 뷰어를 제공합니다.

```text
calf_extensions/media_ffmpeg/   실행기·독립 검사기·씬 선택·CLI
docs/                         영문·한글 사용법과 연결 안내
examples/                     명시적 SDK 사용 예제
VERIFICATION.json             공개 검증 요약
```

비공개 CALF 엔진, 사용자 기록·계약·성향·인증정보와 생성 미디어는 포함하지 않습니다. 소스 설치로 기존 CALF 기록을 이동하거나 다시 쓰지 않습니다.

## 라이선스

[LICENSE-EXTENSIONS.txt](LICENSE-EXTENSIONS.txt)에 따라 CALF 확장 개발을 위한 소스 사용·수정·배포를 허용합니다. 기존 SDK 통합 라이선스는 [LICENSE-SDK.txt](LICENSE-SDK.txt)에 보존했습니다. 이 허용 범위에 CALF 비공개 코어는 포함되지 않습니다. FFmpeg 등 외부 구성 요소에는 각자의 라이선스가 적용됩니다.
