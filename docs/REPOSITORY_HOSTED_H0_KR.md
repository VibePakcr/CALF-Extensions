# H0 공통 소스 계약: 구현과 검증

[English](REPOSITORY_HOSTED_H0.md) · [전체 연동 계획](REPOSITORY_HOSTED_PLAN_KR.md) · [검증 기록](verification/repository-hosted-h0-20261107.json)

2026-11-07 · H0 구현 완료 · macOS 계약/Local UI 검증 · GitHub·GitLab transport는 아직 미구현

`providers/base.py`에 불변 RepositoryIdentity·Revision·Entry·Content·Snapshot·Capabilities와 SourceReader protocol을 추가했습니다. `providers/local.py`의 LocalSource가 기존 GitReader와 v1 수집·원문 읽기를 감싸며, 분석기는 `analyze_snapshot`을 통해 경로와 Git 명령을 모르는 공통 원문 계약만 사용합니다. 기존 `analyze(reader,store,capture,settings)`와 `compare.source` 진입점은 호환 wrapper로 유지합니다.

## 신원과 저장

- 고정 커밋과 로컬 working 상태를 구분합니다. working 원문을 HEAD 커밋 원문이라고 주장하지 않습니다.
- branch/tag 이름을 구분하고 annotated tag를 commit으로 해석합니다. ref를 고정한 뒤에는 브랜치가 움직여도 고정 commit/tree/blob을 읽으며 checkout하지 않습니다.
- READY의 빈 bytes와 ABSENT·NOT_FETCHED·UNAVAILABLE·LIMIT_EXCEEDED를 구분합니다. 완료되지 않은 목록으로 삭제를 판정하지 않습니다.
- v2는 `captures-v2/<snapshot-id>.json`에 새로 저장합니다. v1 파일은 재작성·이동하지 않습니다. 보존된 bytes가 있으면 원래 저장소 없이도 v1 snapshot을 읽을 수 있습니다.
- `snapshot_id`는 기존 v1 capture ID를 유지합니다. 실제 보존 bytes와 availability까지 묶는 `input_id`는 별도입니다. v2에서는 두 값이 같습니다.
- `navigation_id`는 input ID·mapping digest·분석기 버전·지도 schema를 묶습니다. ComparisonContext도 양쪽 input ID를 묶으므로 원문이 미확보된 경우를 같은 완료 결과로 캐시하지 않습니다.
- Snapshot/Content 데이터는 불변이며 취소 event는 신원에 포함하지 않는 별도 실행 상태입니다. 파일 1 MiB·합계 64 MiB와 metadata 한도를 유지합니다.

## 개발 인터페이스

다음은 현재 구현된 Python 인터페이스입니다. 자격증명·HTTP·자동 저장소 등록을 요구하지 않습니다.

```python
from calf_extensions.repository.providers.local import LocalSource
from calf_extensions.repository.providers.base import ComparisonContext
from calf_extensions.repository.analyze import analyze_snapshot
from calf_extensions.repository.compare import compare_pair

source = LocalSource(project_directory, app_data_directory)
revision = source.pin("branch", "main")
snapshot = source.snapshot(revision)
snapshot_id = source.store.save_snapshot(snapshot)
restored = source.store.load_snapshot(snapshot_id)
graph = analyze_snapshot(restored)
# 같은 저장소의 다른 Snapshot을 얻은 뒤:
# result = compare_pair(ComparisonContext(restored, other), path_id)
```

기존 `python -m calf_extensions.repository.cli open --repo ... --data-dir ...`와 v1 코드/Diff·내보내기는 그대로 지원합니다. v2 capture 보존·분석 계약은 구현했지만 v2 지도의 CLI 내보내기는 H4 범위이므로 H0에서는 명시적으로 거절합니다. `sources add`·`open --source`도 아직 구현하지 않았습니다.

## 확인한 범위

기존 22개와 새 H0 12개를 합친 34개 검사가 통과했습니다. 비교 input 신원의 마지막 보강 후 H0 12개를 추가 확인했습니다. FFmpeg 계약 검사 3개, v2 JSON Schema와 실제 직렬화 fixture 검사도 통과했습니다.

macOS Chrome에서 지도·하단 코드·Diff·호출 줄·탐색 복원·한영·1440/390/320 폭·핀치 에뮬레이션을 확인했습니다. 원본을 숨기고 HTTP를 차단한 v1 오프라인 보기 또한 통과했고 시험 서버와 브라우저 프로세스는 종료했습니다. 실제 휴대전화·외부 에디터 실행은 별도 미검증입니다.

GitHub/GitLab 형태의 메모리 snapshot은 같은 파일·심볼·문서·호출 지도를 만들었으며, 이 분석 중 socket과 subprocess 호출을 금지하여 transport/프로젝트 실행에 의존하지 않음을 확인했습니다. 실제 GitHub/GitLab 지원을 검증한 것은 아닙니다. H0 변경분의 Windows·Linux 재검증과 패키징·성능 검증도 아직 하지 않았습니다.

기존 FFmpeg·라이선스·릴리즈 파일 15개, 과거 v1 파일 27개와 기존 보존 집합 565개의 H0 시작 시점 해시가 유지됐습니다. 과거 v1 snapshot 3개를 실제로 읽고도 파일이 그대로임을 확인했습니다. 기존 CALF 기록은 수정하지 않았습니다.

다음 단계는 H1 수동 등록·자격증명 참조·bounded HTTP·작업/취소입니다. 전체 hosted 검증 기준은 아직 NOT_RUN이며 H0는 관련 계약 fixture 근거만 추가합니다.

END
