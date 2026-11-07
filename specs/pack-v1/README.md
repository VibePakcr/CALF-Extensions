# Extension Pack v1 reference artifacts

[English specification](../../docs/EXTENSION_PACK_SPEC.md) · [한국어 규격](../../docs/EXTENSION_PACK_SPEC_KR.md)

Draft specification 0.1.0. These artifacts define metadata, not a pack installer or execution engine. No existing pack is automatically converted to this format.

The [local pack lifecycle preview](../../docs/PACK_MANAGER.md) / [로컬 팩 사용법](../../docs/PACK_MANAGER_KR.md) implements consumers for FFmpeg scenes and [Repository Local Git inspect](../../docs/REPOSITORY_PACK.md). Its `candidate` state supports isolated staging/qualification and explicit experimental activation; it does not make these reference examples installable or qualify planned drivers.

- [Manifest JSON Schema](manifest.schema.json), Draft 2020-12; strict structure with no external schema fetch.
- [FFmpeg reference](examples/ffmpeg.json): existing runtime entry points and narrow core ranges; existing runtime evidence is distinct from unexecuted pack-lifecycle checks.
- [Motion-patch reference](examples/motion-patch.json): planned supervised patch and optional comparison-preview modes; NumPy/OpenCV versions match the current experimental requirements, not a qualified production release.
- [Repository reference](examples/repository.json): planned standalone Local Git navigation; no core/SDK/media dependency. Git 2.43 is the current P0 reader's declared floor, not cross-platform qualification.

All three use `availability: reference` and `verification.lifecycleStatus: NOT_RUN`. They must not be installed as released packs. Planned entry points have no invented executable target. A future release manifest requires real targets, verified package files and qualification receipts.

The schema validates types and local field rules. Host checks must additionally reject duplicate JSON keys/IDs, inverted intervals, dangling dependency/entry-point IDs, invalid transport-target combinations, unqualified released modes and inconsistent evidence; inspect actual files and authority before any action. A syntactically valid manifest cannot grant permissions, attest an OS sandbox or establish native CALF success.

세 예제는 모두 **설치할 수 없는 참조 자료**입니다. 현재 코어·설치 방식·등록·기록·설정에는 적용하지 않습니다. 스키마 검증과 실제 설치·호환·실행 검증을 구분하며, 새 팩 관리 기능이 구현된 뒤 공통 합격 기준을 확인합니다.
