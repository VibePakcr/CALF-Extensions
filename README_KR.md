# CALF Extensions

**문서 개정판 docs.1:** 배포 패키지 안의 영·한 매뉴얼도 최신 교정본으로 맞췄습니다. 실행 코드와 기존 버전은 유지합니다. [변경 내용·검증 범위](DOCUMENTATION-RELEASE-20261107.1.md).

CALF — Controlled Agent Lifecycle Framework에 연결하는 로컬 도구 모음입니다.

[English](README.md) · **[AI와 함께 처음 설치하기](INSTALL_KR.md)** · [CALF 실행기 다운로드](https://github.com/VibePakcr/CALF/blob/main/DOWNLOADS.md)

## 영상 작업 관리 팩 · 0.1.0-preview.1

외부 영상 도구에 보낸 요청부터 결과 파일 수신·검토·채택·재수정까지 기존 CALF 씬 기록으로 관리합니다. 반환 파일의 원본 바이트와 해상도를 보존합니다.

| 시작 순서 | 바로가기 |
|---|---|
| **1. ZIP 다운로드** | **[GitHub](https://github.com/VibePakcr/CALF-Extensions/releases/download/docs-20261107.1/CALF-Video-Work-Management-Pack-0.1.0-preview.1%2Bdocs.1.zip)** · **[GitLab](https://gitlab.com/-/project/88597295/uploads/91b29c940e075497d7ab5951dfdc43c8/CALF-Video-Work-Management-Pack-0.1.0-preview.1+docs.1.zip)** |
| **2. 설치** | **[INSTALL_KR.md — AI와 함께하는 초보자 안내](INSTALL_KR.md)** · [English](INSTALL.md) |
| **3. 사용** | **[실제 캡처가 포함된 단계별 매뉴얼](docs/media-jobs-manual/README_KR.md)** |
| 다른 압축 형식·체크섬·검증 보고서 | [GitHub](https://github.com/VibePakcr/CALF-Extensions/releases/tag/docs-20261107.1) · [GitLab](https://gitlab.com/vibepackr-group/CALF-Extensions/-/releases/docs-20261107.1) |

Python 3.10 이상, 별도 CALF SDK 0.2.1·네이티브 실행기·FFmpeg/ffprobe가 필요합니다. 새 폴더에 압축을 풀어 실행하는 프리뷰이며 의존 도구는 별도로 준비합니다. macOS ARM64·1080p 합성 영상으로 검증했습니다. 이 추가 팩의 Windows/Linux·실제 납품 영상·생성 API 연결은 검증 범위에 포함되지 않습니다.

**요청 → 외부 영상 도구 → 반환 → 검사 → 영상 검토 → 채택 → 재수정.** Gemini/Veo 등과의 전달·다운로드는 수동입니다. 기술 검사가 미적 품질이나 수정 의도 충족 여부를 판정하지는 않습니다.

![합성 반환 영상을 실제 macOS 빠른 보기로 확인하는 화면](docs/media-jobs-manual/images/finder-returned.jpg)

실제 데모 캡처입니다. 네 단계의 전체 화면과 명령은 사용 매뉴얼에서 확인하세요.

## 다른 도구 다운로드

기능마다 설치 요건과 검증 범위가 다릅니다.

| 기능 | 다운로드 | 안내·준비물 |
|---|---|---|
| Repository Navigator · 0.1.0-dev.1 | [GitHub](https://github.com/VibePakcr/CALF-Extensions/releases/tag/docs-20261107.1) · [GitLab](https://gitlab.com/vibepackr-group/CALF-Extensions/-/releases/docs-20261107.1) | [화면 매뉴얼](docs/navigator-manual/README_KR.md). Python·Git. CALF core·SDK는 필요하지 않습니다. |
| Local Pack Tools + Repository Pack · 0.1.0-preview.1 | [GitHub](https://github.com/VibePakcr/CALF-Extensions/releases/tag/docs-20261107.1) · [GitLab](https://gitlab.com/vibepackr-group/CALF-Extensions/-/releases/docs-20261107.1) | [팩 안내](docs/PACKS_GUIDE_KR.md). Python·Git. 로컬 저장소 읽기 전용 작업입니다. |
| FFmpeg 씬 작업 · 0.1.0 | [GitHub](https://github.com/VibePakcr/CALF-Extensions/releases/tag/docs-20261107.1) · [GitLab](https://gitlab.com/vibepackr-group/CALF-Extensions/-/releases/docs-20261107.1) | [FFmpeg 안내](docs/FFMPEG_KR.md). Python·SDK·CALF 실행기·FFmpeg/ffprobe. |

이전 FFmpeg 프리뷰의 [운영체제별 검증](VERIFICATION.json)은 새 영상 작업 관리 팩의 검증과 별개입니다. 기존 배포 파일과 이전 버전은 계속 보관합니다.

## 에이전트·개발자 참고

- [영상 관리 CLI·지원 범위·복구](calf_extensions/media_jobs/README_KR.md)
- [기존 Work MCP·에이전트 연동](docs/AGENTS_KR.md) · [Claude 예제](docs/CLAUDE_KR.md)
- [로컬 팩 안내](docs/PACKS_GUIDE_KR.md) · [프리뷰 팩 명세](specs/pack-v1/README.md)
- [확장 라이선스](LICENSE-EXTENSIONS.txt) · [SDK 라이선스](LICENSE-SDK.txt)

SDK·네이티브 실행기는 별도입니다. 새 버전은 새 폴더에 준비하고 이전 소스·도구 위치, 계약·기록·승인 영상을 보존하세요.

최신 안내 문서는 [문서 체크섬](DOCS-SHA256SUMS)으로 확인할 수 있습니다. 루트의 `SHA256SUMS`는 최초 FFmpeg 0.1.0 패키지의 파일 목록이며, 배포 압축 파일은 해당 릴리즈의 체크섬과 대조하세요. 기존 패키지에는 그 버전의 매뉴얼이 그대로 보관됩니다.
