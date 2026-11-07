# H2 GitHub 고정 ref·tree·blob reader

[English](REPOSITORY_HOSTED_H2.md) · [연동 계획](REPOSITORY_HOSTED_PLAN_KR.md) · [검증 기록](verification/repository-hosted-h2-20261107.json)

2026-11-07 · GitHubSource 구현 · macOS에서 익명 공개 GitHub reader 검증

H2는 사용자가 등록하고 신원을 확인한 GitHub.com 저장소에 공통 SourceReader 계약을 구현합니다. branch·tag·전체 40자리 commit을 고정하고 검증한 목록과 한도가 있는 원문을 수집해 불변 H0 Snapshot을 반환합니다. H1 HTTP 정책에는 SHA로 지정한 annotated tag 읽기 틀 하나를 추가합니다. reader는 계정 전체 등록·프로젝트 코드 실행·활성 지도 게시를 수행하지 않습니다.

## Python reader 사용

선택한 저장소를 등록한 뒤 H1 `sources check SOURCE_ID --data-dir APP_DATA`를 명시적으로 실행합니다. 같은 앱 데이터에서 검증된 등록을 읽습니다. reader는 신원 확인을 요구합니다. canonical 이름이 바뀌면 `REGISTRATION_STALE`을 반환하므로 이름 변경 후에는 명시적으로 확인하고 등록을 다시 읽습니다.

```python
from calf_extensions.repository.registrations import Registry
from calf_extensions.repository.providers.github import GitHubSource
from calf_extensions.repository.capture import Store
from calf_extensions.repository.analyze import analyze_snapshot

registration = Registry(APP_DATA).get(SOURCE_ID)
source = GitHubSource(registration)
try:
    revision = source.pin("branch", "main")  # 또는 ("tag", "v1") / ("commit", FULL_SHA1)
    snapshot = source.snapshot(revision)
    graph = analyze_snapshot(snapshot, SETTINGS)
    # 명시적 보존. 소스 저장소·CALF 기록 밖의 앱 데이터를 사용합니다.
    capture_id = Store(APP_DATA, create=True).save_snapshot(snapshot)
    coverage = source.report
finally:
    source.close()
```

`SETTINGS`는 기존의 선택적 기능·용어집 매핑 dictionary입니다. 선택 수집은 `snapshot`에 `path_ids={path_record(path_bytes)["id"], ...}`를 전달합니다. `path_record`는 `repository.model`에서 가져옵니다. 목록이 완전해도 선택하지 않은 파일은 NOT_FETCHED입니다. 완전한 목록이 모든 원문의 수집·분석을 뜻하지 않습니다. 생성자의 `cancel=threading.Event()`와 `budget=Budget(...)`는 ref 고정부터 수집까지 취소·요청 한도를 공유합니다. 동기 foreground reader이며 H1 신원 확인 job API는 그대로입니다. hosted `open/scan --source`·소스 선택 UI·provider 에디터/permalink·v2 오프라인 내보내기는 H4 범위입니다. 기존 Local Git 명령과 FFmpeg 흐름의 인터페이스를 유지합니다.

## 정확성과 실패 처리

- branch·tag namespace를 구분하고 반환 ref가 정확히 일치하는지 검사합니다. annotated tag는 객체 SHA로 따라가며 순환·대상 종류·깊이를 검사한 뒤 고정 commit/tree를 읽습니다. GitHub reader에서 SHA-256 Git 객체 형식과 암묵적 HEAD/기본 branch 선택은 제공하지 않습니다.
- 등록 숫자 ID와 canonical 이름을 검증합니다. commit·tree·저장소 불일치를 거절합니다. commit→tree 연결은 GitHub가 보고한 값이며 독립적인 raw commit·서명 검증을 했다고 주장하지 않습니다.
- recursive Git Trees 조회가 잘리면 불완전한 목록을 버리고 SHA로 고정한 nonrecursive subtree를 순회합니다. 정확한 UTF-8 이름·mode·Git 정렬로 완전한 tree 바이트를 재구성해 SHA-1을 검증합니다. Contents 디렉터리 조회를 완전한 목록으로 사용하지 않습니다. subtree도 잘리거나 목록 예산이 소진되면 부재를 증명하지 않으며 `inventory_complete=False`와 사유를 표시합니다.
- 선택한 일반 blob만 읽습니다. Base64를 엄격하게 해석하고 응답 크기·목록 크기·blob SHA-1·원문 SHA256을 검증합니다. 0바이트는 실제 READY 빈 파일입니다. 손상·누락·미수집 바이트를 빈 텍스트로 바꾸지 않습니다. binary·BOM·CRLF·비 UTF-8 원문도 정확한 바이트와 텍스트 가용성을 유지합니다.
- symlink·submodule은 대상에 접근하지 않고 항목으로 남기며 LFS pointer는 LFS 객체를 내려받지 않고 원문만 보존합니다. 대체 문자 등 원문이 모호한 API 경로는 명시적으로 실패합니다. 표현 가능한 Unicode·공백·플러스·퍼센트·해시·탭·개행의 바이트 신원은 정규화하지 않습니다.
- H1 목적지·인증·캐시·재시도 제어와 기본 공통 예산 300회/120초를 유지합니다. 총 metadata 32 MiB·목록 항목 50,000개·subtree 128단계·tag 해석 16단계·파일당 1 MiB·원문 합계 64 MiB 제한을 적용합니다. blob 조회를 중복 제거해도 materialized 바이트는 경로별로 계산합니다.
- 요청·사용량·크기 한도는 목록·원문의 부분 결과와 `source.report` 사유로 남길 수 있으며 잘못되거나 불일치한 자료는 실패합니다. 취소·기한 초과는 새로 쓸 snapshot을 반환하지 않습니다. 호출자는 보존·활성화 전에 coverage를 확인해야 합니다. reader가 기존 활성 수집본이나 v1 파일을 변경하지 않습니다.

실제 저장소 검사에서 공통 분석기의 호환성 결함도 발견했습니다. 묶음 import가 같은 관계를 중복 생성하고 같은 줄의 반복 호출은 위치가 구분되지 않았습니다. `python-ast-v3`는 동일 관계를 중복 제거하고 AST 시작/종료 열을 추가해 호출 위치를 보존합니다. 열은 0부터 시작하는 UTF-8 바이트 위치이며 끝 위치는 미포함입니다. analyzer/navigation 신원도 달라지며 과거 수집본·지도는 다시 쓰지 않습니다.

## 실제 검증

최종 저장소 검사 **81개: 이전 62 + H2 19**와 FFmpeg 계약 검사 3개가 통과했습니다. H2는 독립적으로 생성한 실제 Git 객체로 ref 이동·동명 충돌·annotated tag·완전/잘린 tree·1,005개 파일 디렉터리·정확한 경로/바이트/mode·손상·크기/예산 누락·취소·v2 보존 재로딩·Local/GitHub 정규화 지도 및 직접 Diff를 검사했습니다. 소유한 HTTP subprocess로 annotated tag endpoint도 시험했습니다.

실제 익명 GitHub API는 공개 [VibePakcr/CALF-Extensions](https://github.com/VibePakcr/CALF-Extensions)의 고정 commit `66bdf4a6e8d19ec87b4a10b9e541f1fe3870dc02`와 API 버전 `2026-03-10`을 사용했습니다. **목록 56개 전체**가 독립 로컬 Git 객체와 일치했고 **선택 원문 13개 / 82,756바이트**가 정확히 일치했습니다. 정규화 지도도 일치했으며 225개 노드·516개 관계를 확인했고 보존 v2를 그대로 다시 읽었습니다. 성공 시도는 **19회 요청 / 9.688초**입니다. 앞선 실제 지도 실패와 로컬 진단은 별도로 보존했습니다.

새로운 실제 macOS Chrome의 Local 실시간·오프라인 회귀 검사에서 지도·코드·Diff·호출 줄·북마크·영·한 전환·핀치 에뮬레이션·1440/390/320 폭이 런타임 오류 없이 통과했습니다. 오프라인 열기 때 원래 fixture 소스를 숨겼습니다. 이는 Local UI 회귀 근거이며 hosted 소스 UI는 아직 구현하지 않았습니다. 서버·소켓·소유 시험 브라우저를 정리했습니다.

FFmpeg·라이선스·릴리즈 파일, 과거 v1 자료, 기존 CALF 자료, H0/H1 문서·검증 기록 6개, 다른 작업의 README·패키지 변경은 기준 해시를 유지했습니다. 더 넓은 607개 보존 집합 중 **606개가 동일**했고 외부 앱 런타임 설정 1개에서 작업 중 변경을 관측했습니다. 본 작업에서 해당 설정 내용을 수정·복구하지 않았습니다. 기존 프로세스 제한 fixture에서 OS `killpg` EPERM이 한 번 발생했으나 변경 없는 단독 재검사와 후속 전체 검사는 통과했습니다. 최초 실패를 검증 기록에 남기며 간헐적 OS 원인이 H2로 해결됐다고 주장하지 않습니다.

GitLab 수집(H3), 실제 비공개 접근, 실제 annotated tag·tree 잘림·경로 경계 사례, H2 Windows·Linux, hosted 지도 UI·내보내기(H4), 새 패키지 설치, 성능·최대 메모리 검증·실기기는 NOT_RUN입니다. 전체 HG01–HG32 판정은 NOT_RUN으로 유지하고 GitHub 공개 reader의 범위가 한정된 진행을 따로 기록합니다. provider 쓰기·clone/fetch/push·소유자 자격증명 사용·native CALF 기록 쓰기·커밋/push는 수행하지 않았습니다.

계약: [Git Trees](https://docs.github.com/en/rest/git/trees#get-a-tree), [Git blobs](https://docs.github.com/en/rest/git/blobs#get-a-blob), [Git refs](https://docs.github.com/en/rest/git/refs#get-a-reference), [annotated tags](https://docs.github.com/en/rest/git/tags#get-a-tag), [Git commits](https://docs.github.com/en/rest/git/commits#get-a-commit).

