# FFmpeg Extension 0.1.0 — Developer Preview

[English](#english) · [한국어](#한국어)

## English

This first packaged CALF extension renders and checks one scene candidate, selects a validated version without overwriting prior approval, and retains earlier versions for recovery.

- macOS ARM64 / FFmpeg 8.1.2, Windows 11 x64 / FFmpeg 9.0.2 and Debian 13 x64 / FFmpeg 7.0.2 passed 13 acceptance groups each, including three contract unit tests.
- Tests cover three approved scenes, scene-3-only replacement, unchanged scene-1/2 hashes and pointers, rejected width/black/silence candidates, stale evidence, idempotent requests, read-only reconciliation, MCP boundaries and restoration without rendering.
- A real macOS Claude Code 2.1.201 session performed inspect → step → inspect. CALF returned current `SATISFIED` evidence before host-authorized selection. The first pending-MCP trial was retained; the corrected flow waits for connection before the model request.
- English/Korean installation, upgrade, FFmpeg and Claude guides and a default model-free Claude readiness example are included.

Use the same ZIP or tar.gz on the tested operating systems. Native CALF 1.8.7/1.9.2, SDK 0.2.1, Python and FFmpeg/ffprobe are separate prerequisites. No proprietary core, SDK copy, third-party executables, models, credentials, existing records or generated videos are bundled. Verify downloads with the release SHA256SUMS; the package contains its own per-file SHA256SUMS.

Extract into a new folder and retain referenced old code/tool paths and the complete records/scene project. Contracts and attempt budgets are not migrated or reset. Validation is technical, using short synthetic MP4s; artistic review, production footage, Claude Desktop GUI integration and other generation runtimes remain outside qualification. See VERIFICATION.json for exact scope and package checks.

## 한국어

첫 배포 패키지는 씬 하나의 후보를 렌더링·검사하고, 기존 승인본을 덮어쓰지 않은 채 검증된 버전을 선택합니다. 이전 버전은 복원할 수 있도록 보존합니다.

- macOS ARM64 / FFmpeg 8.1.2, Windows 11 x64 / FFmpeg 9.0.2, Debian 13 x64 / FFmpeg 7.0.2에서 각각 13개 수락 항목을 통과했습니다. 계약 단위 검사 3개가 포함됩니다.
- 승인 씬 3개, 3번만 교체, 1·2번 해시·선택 버전 유지, 규격·검은 화면·무음 후보 거부, 오래된 증거 무효화, 중복 요청, 읽기 전용 복구 조회, MCP 경계, 재렌더 없는 복원을 확인했습니다.
- macOS의 실제 Claude Code 2.1.201이 조회 → 실행 → 재조회를 수행했습니다. CALF의 현재 `SATISFIED` 증거를 확인한 뒤 호스트가 승인한 선택을 적용했습니다. MCP 준비 전 전송했던 첫 실패 기록도 보존했으며, 수정한 흐름은 연결 완료 후에만 모델에 요청합니다.
- 영한 설치·업데이트·FFmpeg·Claude 안내와 기본적으로 모델을 호출하지 않는 Claude 연결 확인 예제를 포함합니다.

검증된 OS에서 같은 ZIP 또는 tar.gz를 사용합니다. 네이티브 CALF 1.8.7/1.9.2·SDK 0.2.1·Python·FFmpeg/ffprobe는 별도로 준비합니다. 비공개 코어·SDK 사본·외부 실행 파일·모델·인증정보·기존 기록·생성 영상을 동봉하지 않습니다. 릴리즈 SHA256SUMS로 다운로드를 확인하세요. 패키지 내부에는 파일별 SHA256SUMS도 있습니다.

새 폴더에 압축을 풀고 기존 작업이 참조하는 코드·도구 경로와 전체 기록·씬 프로젝트를 보존하세요. 계약을 이전하거나 시도 예산을 초기화하지 않습니다. 짧은 합성 MP4의 기술 검수 기준이며 미적 검수·실제 제작 영상·Claude Desktop GUI 연결·다른 생성 런타임은 검증 범위 밖입니다. 세부 범위와 패키지 검사는 VERIFICATION.json에 기록합니다.
