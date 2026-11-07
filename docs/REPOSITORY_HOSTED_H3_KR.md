# H3 GitLab 고정 ref·tree·raw blob reader

[English](REPOSITORY_HOSTED_H3.md) · [연동 계획](REPOSITORY_HOSTED_PLAN_KR.md) · [검증 기록](verification/repository-hosted-h3-20261107.json)

2026-11-07 · GitLabSource 구현 · macOS Git 기반 fixture와 범위를 한정한 공개 raw 읽기 검증

H3는 공통 SourceReader 구현인 `providers/gitlab.py`를 추가합니다. 수동 등록·신원 확인한 GitLab.com 프로젝트의 종류를 명시한 ref를 전체 SHA-1 commit으로 고정하고, 그 commit의 페이지별 목록과 한도 안의 raw blob 바이트를 수집합니다. 기존 GitHubSource·Local Git·HTTP 정책·분석기·CLI·UI 자산·FFmpeg·CALF 기록은 그대로입니다.

## Reader 인터페이스

선택한 프로젝트를 등록하고 H1 `sources check SOURCE_ID --data-dir APP_DATA`를 명시적으로 실행한 뒤 검증된 등록을 읽습니다. GitLab subgroup은 H1 등록에서 지원하며 수집에는 연결된 숫자 프로젝트 ID를 사용합니다.

```python
from calf_extensions.repository.registrations import Registry
from calf_extensions.repository.providers.gitlab import GitLabSource
from calf_extensions.repository.capture import Store
from calf_extensions.repository.analyze import analyze_snapshot

source = GitLabSource(Registry(APP_DATA).get(SOURCE_ID))
try:
    revision = source.pin("branch", "main")  # 또는 ("tag", "v1") / ("commit", FULL_SHA1)
    snapshot = source.snapshot(revision)
    graph = analyze_snapshot(snapshot, SETTINGS)
    capture_id = Store(APP_DATA, create=True).save_snapshot(snapshot)
    coverage = source.report  # 필요하면 snapshot과 함께 직렬화한 사본을 보존합니다.
finally:
    source.close()
```

`SETTINGS`는 기존의 선택적 기능·용어집 dictionary입니다. 앱 데이터는 소스 저장소와 기존 CALF 기록 밖에 둡니다. `snapshot(revision, path_ids={...})`는 `model.path_record(raw_path_bytes)["id"]`로 명시적 원문 선택을 지원합니다. 선택하지 않은 파일은 NOT_FETCHED입니다. 생성자 `cancel=threading.Event()`·`budget=Budget(...)`는 고정·페이지·blob 수집의 작업 한도를 공유합니다. 동기 reader는 불변 Snapshot을 반환하며 자동 저장·활성화하지 않습니다. H1 job 경로는 계속 신원 확인 전용입니다. hosted 소스 선택 UI·`open/scan --source`·provider 에디터/permalink·v2 오프라인 내보내기는 H4 범위입니다.

## Ref·목록·바이트 의미

- branch·tag·전체 commit 요청을 구분하고 반환 이름이 정확히 일치하는지 검사합니다. annotated tag는 tag endpoint의 해석된 `commit.id`를 사용합니다. 후속 commit/tree는 고정한 전체 commit, raw blob은 목록의 SHA로 읽습니다. 잘못된 ref는 접속 전에 실패합니다. 숫자 프로젝트 ID·canonical namespace를 검증하며 이름이 바뀌면 명시적인 H1 확인·재로딩이 필요합니다.
- `Revision.tree_oid=None`을 유지합니다. 사용하는 GitLab commit API는 root tree OID를 제공하지 않습니다. `source.report.tree_oid_reason`은 `NOT_EXPOSED_BY_GITLAB_COMMIT_API`를 기록하며, 재열기 때 사유가 필요하면 report도 보존합니다. 목록 digest는 별도의 정규화 SHA256이며 Git tree 신원이 아닙니다. commit→목록 연결·완전성은 API 보고값이며 독립적인 raw commit/root tree 증명이 아닙니다.
- recursive tree를 `ref=FULL_COMMIT`, `pagination=keyset`, `per_page=100`으로 읽습니다. H1은 next 링크의 origin·숫자 프로젝트·endpoint·고정 ref·인수를 검증하며 페이지도 같은 요청·인증·취소 예산을 사용합니다. 경로/페이지 중복·커서 순환·잘못된 링크·완전한 목록의 부모 누락·mode 충돌은 명시적으로 실패합니다. total-count 헤더를 요구하거나 완전성 근거로 삼지 않습니다.
- 짧은 마지막 페이지에 next 링크가 없으면 API 목록을 완료합니다. 100개짜리 페이지에 next 정보가 없으면 실제 마지막 페이지일 가능성이 있어도 `PAGINATION_END_UNKNOWN`과 불완전 목록으로 보수적으로 처리합니다. 불완전 목록으로 부재를 추론하지 않습니다. 유효한 빈 tree와 접근 불가/누락 404는 구분합니다.
- 원문은 **`/repository/blobs/SHA/raw`만** 읽습니다. JSON file/blob 응답은 비 UTF-8 내용을 변환할 수 있어 원문으로 사용하지 않습니다. raw 바이트 수·Git blob SHA-1·SHA256을 확인합니다. 빈 값·BOM·CRLF·binary·비 UTF-8·텍스트 미지원·NOT_FETCHED를 구분합니다. MIME이 JSON이어도 raw 파일 바이트를 JSON으로 해석하지 않습니다.
- Unicode의 다른 표기와 Git이 허용하는 제어 문자를 포함해 UTF-8 경로 바이트를 정규화하지 않습니다. 잘못된 경로·상위 이동·모호한 대체 문자·이름/mode/type 불일치를 거절합니다. symlink/submodule은 대상에 접근하지 않고 LFS pointer도 LFS 다운로드 없이 원문으로 남깁니다.
- H1의 고정 HTTPS origin·인증 참조·캐시 격리·사용량 제한·소유 worker 취소를 유지합니다. 기본 예산은 300회/120초이며 총 metadata 32 MiB·목록 항목 50,000개·경로 128단계·raw 파일 1 MiB·원문 합계 64 MiB를 제한합니다. 같은 blob은 한 번 읽지만 materialized 바이트는 경로별로 계산합니다.
- 예산·사용량·크기 누락은 목록/원문 coverage와 report 사유에 표시합니다. 손상·접근·계약 실패는 실패하고 취소·기한 초과는 새로 쓸 Snapshot을 반환하지 않습니다. 호출자는 보존·활성화 전에 coverage를 확인합니다. reader가 기존 활성 지도·수집본·권한·CALF receipt를 바꾸지 않습니다.

## 실제 검증

최종 저장소 검사 **101개: 기존 81 + H3 20**과 FFmpeg 계약 검사 3개가 통과했습니다. Git 기반 fixture는 annotated tag/branch 동명 충돌·ref 이동·정확한 Unicode/raw 바이트/mode·1,005개 항목의 페이지 목록·next 범위/순환/중복·페이지 정보 누락·빈 값과 404·원문/metadata 한도·손상·취소·v2 보존 재로딩·완전한 정규화 Local/GitLab 지도와 직접 Diff 일치를 검사합니다. 실제 소유 HTTP subprocess는 JSON MIME에서도 비 UTF-8 raw 바이트를 보존했고 멈춘 raw 읽기를 Snapshot 게시 없이 취소했습니다.

실제 익명 읽기는 기존 공개 [GitLab CALF-Extensions 미러](https://gitlab.com/vibepackr-group/CALF-Extensions)의 프로젝트 `88597295`, 고정 commit `814b6c27fe9ac68ad3f9bb6db7fe2e8ba95f65d1`을 사용했습니다. 목록은 **파일 32개**입니다. **선택 Python 원문 10개 / 53,473바이트**가 같은 경로의 독립 보존 로컬 Git blob과 일치했고 선택 코드의 관계 부분도 일치했습니다. 전체 원격 지도는 163개 노드·508개 관계입니다. 성공 시도는 **20회 요청 / 17.031초**이며 보존 v2를 그대로 다시 읽었습니다. 목록을 두 번 수집했고 각각 한 페이지였습니다. 실제 서비스에서 여러 페이지를 읽는 동작까지 검증한 것은 아닙니다.

미러 최신 commit을 로컬 저장소에서 읽을 수 없었고, 로컬 H2 기준 commit도 미러 API에서 읽을 수 없었습니다. 앞선 두 시도를 보존했습니다. 성공한 실제 검사는 두 고정 commit 사이에 보존된 선택 blob·코드 관계 부분을 대조합니다. **같은 커밋 전체에 대한 Local/GitLab 목록·지도 일치는 NOT_RUN**입니다. 전체 동등성은 독립 합성 Git 시험 자료에서 확인했습니다. 실제 미러 검사에서는 그 범위까지 확인하지 못했습니다.

GitHubSource와 공통 분석기·UI·HTTP를 포함한 **기존 저장소 소스 32개**, 과거 H0–H2 문서·검증 기록 9개, 다른 작업의 README·패키지 변경은 H3 시작 때의 해시를 유지했습니다. 최초 보존 검사에서는 607개 모두 일치했고 최종 검사에서는 **606/607개**가 일치했으며 외부 앱 런타임 설정 1개의 변경을 관측했습니다. 본 작업에서 해당 설정을 수정·복구하지 않았고 두 관측을 모두 보존했습니다. native CALF 기록 쓰기·provider 쓰기·clone/fetch/push·소유자 자격증명 사용·커밋/push는 수행하지 않았습니다. 소유 worker·thread를 정리했습니다. 기존 H2 실제 Chrome live/offline 근거는 소스·자산 해시 일치를 확인하고 재사용하며 새 브라우저·원격 소스 UI를 새로 검증한 결과는 아닙니다.

비공개 GitLab 접근, 실제 tag·Unicode·다중 페이지 경계 사례, Self-Managed, SHA-256 Git 객체, H3 Windows·Linux, hosted UI·내보내기, 새 패키지 설치, 성능·최대 메모리·실기기는 NOT_RUN입니다. 전체 HG01–HG32는 NOT_RUN으로 유지하고 H3 reader의 검증한 범위의 진행 결과만 추가합니다. 다음은 H4 공통 소스 선택·지도·코드·Diff 흐름입니다.

계약: [repository tree·raw blob](https://docs.gitlab.com/api/repositories/), [branches](https://docs.gitlab.com/api/branches/), [tags](https://docs.gitlab.com/api/tags/), [commits](https://docs.gitlab.com/api/commits/), [페이지](https://docs.gitlab.com/api/rest/#pagination).

