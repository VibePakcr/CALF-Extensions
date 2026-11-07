# GitHub·GitLab 프로젝트 탐색 연동 구현 계획

[English](REPOSITORY_HOSTED_PLAN.md) · [검증 기준 JSON](REPOSITORY_HOSTED_ACCEPTANCE.json) · [현재 Local Git 계획](REPOSITORY_LOCAL_GIT_PLAN_KR.md)

기준: `66bdf4a6e8d19ec87b4a10b9e541f1fe3870dc02` · 2026-11-07 · **H0–H5 공개·데스크톱 범위 검증, 비공개·전체 행렬은 미완료**

공통 계약은 [H0 기록](REPOSITORY_HOSTED_H0_KR.md), 수동 등록·인증 참조·제한된 HTTP·취소 가능한 신원 확인은 [H1 기록](REPOSITORY_HOSTED_H1_KR.md)을 확인하십시오. [H2 기록](REPOSITORY_HOSTED_H2_KR.md)은 GitHub 고정 reader와 범위가 한정된 익명 공개 검증을 추가합니다. [H3 기록](REPOSITORY_HOSTED_H3_KR.md)은 GitLab 고정 tree/raw blob과 범위를 한정한 공개 보존 blob 대조를 추가합니다. [H4 기록](REPOSITORY_HOSTED_H4_KR.md)은 공통 소스 선택·지도·코드/Diff·이력·에디터 사본·v2 오프라인과 macOS Git 기반 provider UI fixture 검증을 추가합니다. [H5 기록](REPOSITORY_HOSTED_H5_KR.md)은 실제 공개 저장소와 데스크톱 3종의 검증 결과·macOS 새 설치·측정 범위를 기록합니다. 비공개·전체 행렬은 미완료입니다.

## 1. 목표와 첫 범위

사용자가 등록한 GitHub·GitLab 저장소를 기존과 같은 프로젝트 지도와 맵 아래 설명·코드·Diff 패널로 탐색합니다. Git은 버전·원문을 제공하며 기능·문서·소스 연결이 주 탐색 경로입니다.

첫 범위는 GitHub.com·GitLab.com의 공개/비공개 저장소, branch·tag·전체 commit ID 선택, 명시적 새로고침, 같은 저장소 안의 두 고정 커밋 비교입니다. 계정·조직 전체 검색, 자동 저장소 등록, clone/checkout, 원격 쓰기, PR/MR·CI 통합, Enterprise/Self-Managed, Rust·JS/TS 호출 분석은 첫 범위에 넣지 않습니다. Python AST·문서 링크·사용자 기능/용어 매핑을 재사용합니다.

사용 흐름은 등록한 저장소 선택 → branch/tag/commit 선택 → 원문·지도 수집 → 노드/관계 선택 → 맵 아래 상세·코드 → 비교 양쪽 선택 → Diff입니다. 새로고침은 사용자 요청으로만 시작하며 계정 연결만으로 다른 저장소를 읽지 않습니다.

## 2. 현 코드에서 먼저 분리할 경계

| 현재 구현 | 필요한 변경 |
| --- | --- |
| `viewer.Project`가 `GitReader`와 로컬 `Store`를 직접 생성 | 등록 소스별 provider 생성과 공통 snapshot을 사용 |
| `analyze`가 로컬 `root`와 `source(..., working)`을 사용 | 불변 snapshot의 원문 읽기 계약으로 분석; 프로젝트 코드를 import/실행하지 않음 |
| `capture`가 worktree·index·로컬 경로를 필수로 가정 | 로컬 v1 호환 adapter와 원격 v2 capture를 구분 |
| `compare`·API·내보내기가 head/index/working에 고정 | 명시적 버전 쌍과 source capabilities로 처리 |
| UI 상태가 capture 중심이며 내보내기가 로컬 경로를 검사 | 등록·snapshot·지도 신원과 provider별 경로/내보내기 정책을 반영 |

가짜 로컬 디렉터리나 index를 만들어 원격 데이터를 끼워 넣지 않습니다. 첫 단계는 이 경계를 실제 계약으로 분리하고 기존 Local Git 동작이 유지되는지 확인하는 것입니다.

## 3. 공통 데이터 계약

```text
Registration = {id, provider, api_origin, stable_repo_id, canonical_web_url,
                ref_kind, ref_name, credential_ref?, project_map_ref?}
Revision = {repository_key, requested_ref, resolved_commit, tree_oid?,
            observed_at, object_format_status}
Snapshot = {schema:v2, source_kind, registration_id, revision, inventory,
            content_manifest, coverage, captured_at, predecessor?}
Navigation = {snapshot_id, navigation_id, mapping_digest, analyzer_version,
              nodes, edges, provenance, coverage}
Content = {path_id, mode, provider_blob_oid?, byte_sha256?, size?,
           availability, kind, encoding?, raw_bytes?}
CompareContext = {repository_key, left_revision, right_revision, basis,
                  left_inventory, right_inventory, changed_paths, coverage}
Capabilities = {working,index,conflict_stages,immutable_revision,
                provider_permalink,cached_copy_editor,offline_export}
```

`repository_key`는 provider·API host·고정 저장소 ID의 조합입니다. 이름·URL은 변경 가능한 표시 속성이며 동명 로컬/원격 저장소를 자동 병합하지 않습니다. `registration_id`는 사용자 앱 데이터의 별도 ID입니다.

등록 시 ref는 종류와 이름을 따로 보관합니다. 수집 시작에 전체 commit ID로 한 번 해석한 뒤 그 커밋/트리/blob만 읽습니다. 수집 중 브랜치가 움직여도 기존 고정 수집을 섞지 않고, 다음 갱신에서 새 수집본을 만듭니다. GitLab API에서 Git tree OID를 확보하지 못하면 null과 사유를 남기고, 정규화한 목록 해시를 Git tree SHA로 부르지 않습니다.

`navigation_id = hash(snapshot_id, mapping_digest, analyzer_version, graph_schema)`로 정의하여 같은 코드라도 기능 매핑·분석기 변경에 따른 지도를 구분합니다. v1의 기존 capture/지도/링크는 원본 파일을 재작성하지 않고 호환 경로로 읽습니다. 새 버전은 별도 불변 파일로 보존합니다.

원문 availability는 `READY / ABSENT / NOT_FETCHED / UNAVAILABLE / LIMIT_EXCEEDED / IDENTITY_MISMATCH`를 구분합니다. 빈 파일은 READY·0바이트·실제 SHA256이고, ABSENT는 완료된 고정 목록에서만 증명합니다. provider OID와 실제 바이트 SHA256을 따로 보관하며 object format이 불명확하면 추측 검증을 하지 않습니다.

## 4. Provider 수집 방식과 공식 API 근거

| 작업 | GitHub | GitLab |
| --- | --- | --- |
| 등록 신원 | 지정 repo 조회 후 고정 ID 확인 | 지정 namespace/project를 조회한 뒤 numeric project ID 사용 |
| ref 고정 | branch/ref, annotated tag 해제, Git commit/tree | branch/tag의 commit ID 및 commit 조회 |
| 파일 목록 | 고정 tree OID의 Git Trees; 잘리면 하위 트리 순회 | 고정 commit의 repository tree; 검증된 keyset/next 페이지 순회 |
| 원문 | tree가 지정한 Git blob OID를 읽고 Base64 해제 후 바이트/OID 확인 | 고정 목록의 blob OID로 **raw blob endpoint** 사용 |
| 비교 | 두 커밋의 목록과 원문을 공통 비교기로 처리 | 같은 공통 비교기로 처리 |
| 실행/쓰기 | 허용한 읽기 endpoint만 사용 | 동일; 임의 GET도 허용하지 않음 |

GitHub의 재귀 트리에는 잘림 표시와 한도가 있고 Contents 디렉터리 목록에도 제한이 있으므로, 목록 완료 여부는 별도 판단합니다. [GitHub Trees](https://docs.github.com/en/rest/git/trees#get-a-tree), [Contents](https://docs.github.com/en/rest/repos/contents#get-repository-content).

**GitLab의 JSON 파일/blob 응답은 일부 인코딩의 원문을 UTF-8로 변환할 수 있습니다.** 정확한 바이트의 근거는 raw blob으로 확보하고 로컬 fixture와 대조합니다. [Repository blobs](https://docs.gitlab.com/api/repositories/#retrieve-raw-blob-content), [Repository files](https://docs.gitlab.com/api/repository_files/#get-file-from-repository).

GitLab tree의 페이지·없는 경로 상태는 API 계약대로 처리합니다. 총수 헤더가 없다는 이유로 목록 완료를 추측하지 않습니다. [Tree API](https://docs.gitlab.com/api/repositories/#list-all-repository-trees-in-a-project), [페이지 처리](https://docs.gitlab.com/api/rest/#pagination).

GitHub API 버전은 구현 시작에 공식 지원 버전을 확인해 상수로 고정하고 fixture/실제 검증서에 기록합니다. GitLab은 v4 endpoint와 실제 확인한 서비스 capability를 기록합니다. beta·feature-flag 전용 API나 archive의 LFS 자동 포함에 의존하지 않습니다.

## 5. 코드와 Diff의 의미

기본 비교는 **선택한 두 불변 snapshot의 직접 비교**입니다. 두 완료된 파일 목록의 합집합에서 path·mode·blob 차이를 찾아 변경 경로를 만들고, 선택한 파일의 양쪽 원문으로 공통 Diff를 계산합니다. 초기 기본 왼쪽은 선택 커밋의 첫 부모로 표시하고, 부모 없는 커밋은 증명된 빈 시작 상태와 비교합니다. 사용자는 양쪽을 직접 바꿀 수 있습니다.

provider의 compare/patch는 힌트이며 전체 파일 목록이나 원문을 대신하지 않습니다. GitHub compare 파일 목록의 한계, GitLab `compare_timeout`·`collapsed`·`too_large`를 반영합니다. [GitHub compare](https://docs.github.com/en/rest/commits/commits#compare-two-commits), [GitLab compare](https://docs.gitlab.com/api/repositories/#compare-branches-tags-or-commits).

직접 비교와 merge-base 비교는 별도 basis입니다. 첫 버전의 필수 화면은 직접 비교이며 merge-base 모드는 검증 후 별도 capability로 켭니다. provider의 기본 비교 의미를 직접 비교라고 표시하지 않습니다.

rename은 provider 힌트와 원문 신원을 구분합니다. 대응을 확정하지 못하면 추가/삭제로 남깁니다. 삭제·이름 변경 파일은 compare context의 경로를 통해 읽고, 현재 지도에 존재하는 파일인 것처럼 만들지 않습니다. 바이너리·인코딩 미지원·원문 미확보는 textual Diff 미확보이며 빈 Diff가 아닙니다.

## 6. 등록·인증·HTTP·범위

등록 정보는 앱 데이터에 저장하고 source URL·ref·표시명·자격증명 **참조**만 포함합니다. 초기 자격증명 방식은 공개 저장소의 anonymous와 서버 환경 변수 참조입니다. CLI token 값 인수·URL 삽입·브라우저 token 입력/저장·기존 자격증명 자동 탐색은 제공하지 않습니다. OAuth·키체인·gh/glab 연동은 후속입니다.

GitHub는 지정 저장소의 Contents 읽기와 필요한 Metadata 읽기 권한을 사용하는 fine-grained token을 기준으로 검증합니다. GitLab은 전체 읽기 API 경로에 `read_api`를 기준으로 검증하며, 파일 API에 가능한 `read_repository`를 모든 endpoint 권한으로 간주하지 않습니다. 쓰기 권한을 요구하거나 실패 후 자동으로 권한을 넓히지 않습니다. [GitHub 권한](https://docs.github.com/en/rest/git/trees#get-a-tree), [GitLab 인증](https://docs.gitlab.com/api/rest/authentication/), [파일 접근 scope](https://docs.gitlab.com/api/repository_files/#available-scopes-for-personal-access-tokens).

transport는 알려진 HTTPS API origin, 저장소 ID, endpoint 틀과 허용 query만 사용합니다. token은 해당 origin의 인증 헤더에만 전달합니다. next/redirect 링크도 origin·endpoint·저장소·고정 ref를 재검증하고 재인증 정보가 다른 대상으로 넘어가지 않게 합니다. 소스 등록 자체는 임의 URL 프록시 권한이 아닙니다.

| 초기 한도/정책 | 계획 값과 처리 |
| --- | --- |
| 원문 | 파일 1 MiB·수집 합계 64 MiB; 실제 스트림 크기도 검사 |
| 응답/지도 | JSON 응답 16 MiB·보존 메타데이터 32 MiB·노드 50,000·관계 100,000; 초과는 해당 범위 미완료 |
| 수집 예산 | 작업당 요청 300회 이하, provider 잔여량보다 작게 조정; page/재시도도 포함 |
| 시간 | metadata 120초·원문/분석 180초·전체 300초 이내; 예산 종료를 완료로 표시하지 않음 |
| HTTP | origin/credential별 순차 큐; I/O timeout 5초; 취소 확인 즉시, 소유 요청 정리는 10초 이내 목표 |
| 재시도 | 전송 실패/5xx의 허용 GET만 최대 2회; provider 대기 시각을 침범하지 않음 |
| 제한 응답 | Retry-After/reset 시각과 RATE_LIMITED를 반환; 예산 밖 대기는 자동 무한 반복하지 않음 |
| 캐시 | 등록·origin·repo ID·자격증명 구획·고정 commit/blob별 분리; ETag는 검증된 대응 캐시가 있을 때만 사용 |
| 범위 | inventory/source/analysis/diff를 각각 표시; 분석 후보와 수집·제외·실패 수를 기록 |

rate limit과 조건부 요청은 공식 계약을 따릅니다. [GitHub 권장 방식](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api), [GitLab REST](https://docs.gitlab.com/api/rest/).

실패·취소·신원 불일치는 기존 활성 수집을 교체하지 않습니다. 일관된 부분 수집본은 별도 보존합니다. 이전 완료 수집이 있으면 부분 후보를 자동으로 활성화하지 않고 사용자에게 선택을 제공합니다. 최초 부분 결과도 범위 표시를 포함합니다. 접근 철회가 이미 보존한 원문을 지웠다고 주장하지 않으며 캐시 보기는 수집 시각·접근 실패와 함께 표시합니다.

## 7. 동일 화면과 기존 사용법

수집은 활성 payload 락 밖에서 수행합니다. 작업별 후보를 만들고 제한된 진행 상태를 제공한 뒤 취소·선택 generation을 확인하여 짧은 락 안에서 일관된 수집/지도 쌍을 게시합니다. 다른 화면에서는 이전 정상 수집본을 계속 열 수 있어야 합니다. DNS·TLS 정리도 제한하며 선택한 transport가 이를 중단하지 못하면 소유 범위가 분명한 취소 가능 worker process를 사용합니다. 읽기 timeout만 설정했다고 취소 검증 완료로 보지 않습니다.

새 로컬 수집·진행·취소 API는 자료형이 정해진 JSON(초기 본문 한도 8 KiB)을 받으며, 기존 루프백 Host·Origin·bearer 검사를 적용합니다. 등록 ID와 종류를 명시한 ref만 받고 provider token이나 임의 fetch URL은 받지 않습니다. 기존 Local Git CLI·refresh 계약도 유지합니다. 수집을 조작하는 로컬 POST가 provider POST/쓰기 권한이 되지 않습니다. 자격증명이 바뀌면 credential-session 캐시 구획도 갱신하며 보존 원문 보기는 역사 자료로 표시합니다.


소스 선택기에 Local/GitHub/GitLab 등록을 표시하고, 원격 branch/tag/commit 선택과 비교 양쪽을 추가합니다. 맵 선택은 전체 맵 아래 설명·기능·원문·줄·SHA와 함께 갱신합니다. code 버전을 바꿔도 지도는 분석 시점에 속함을 표시하고, 지도를 바꾸려면 새 버전 분석을 명시적으로 요청합니다. 늦게 도착한 응답은 이전 선택의 패널을 덮지 못합니다.

원격에는 index·working·conflict stage가 없으므로 해당 조작을 표시하지 않습니다. 원격 원문 permalink는 고정 commit을 사용합니다. 에디터는 명시적으로 만든 보존 사본 또는 commit/blob이 일치하는 등록 로컬 파일에만 연결합니다. 보존 사본을 원격 편집 경로라고 표시하지 않습니다. 에디터 사본은 원격 경로를 그대로 파일 경로로 쓰지 않고 안전한 로컬 이름과 원문 신원을 사용합니다. 원문·저장소 문서는 escape한 텍스트로 표시하며 프로젝트 HTML/script를 실행하지 않고 미지원 인코딩을 손실 대체 문자로 바꾸지 않습니다.

내보내기는 보존된 원문/비교만 사용합니다. 원문은 기본 제외, origin URL·비공개 이름 정보도 별도 명시 포함으로 처리하고 기본 projection은 비식별 source key와 바이트 근거를 유지합니다. 토큰·자격증명 참조·개인 경로는 제외합니다. 데이터 공유 범위는 manifest에 기록합니다.

`sources add/list/remove/check`와 `probe --source`는 H1에서 구현했습니다. 신원 확인 전용 의미와 데이터 경로 인수는 H1 문서를 따릅니다. H4에서 `open/scan --source`와 보존본 `open/export --view`를 구현했습니다. [H4 사용법과 검증 범위](REPOSITORY_HOSTED_H4_KR.md)를 확인하십시오.

```text
calf-repo sources add --provider github --url https://github.com/OWNER/REPO --credential-env MY_GH_TOKEN
calf-repo sources add --provider gitlab --url https://gitlab.com/GROUP/SUBGROUP/PROJECT --credential-env MY_GL_TOKEN
calf-repo sources list
calf-repo open --source SOURCE_ID --ref-kind branch --ref main
calf-repo scan --source SOURCE_ID --ref-kind branch --ref main --project-map CONFIG_FILE
```

기존 `open/scan/probe --repo ...`와 `export --data-dir ... --capture ...`는 유지합니다. `--repo`와 `--source`는 상호 배타적입니다. 등록 해제는 수집본 자동 삭제가 아니며 삭제는 별도 사용자 선택으로 둡니다.

## 8. 구현 순서와 종료 조건

| 단계 | 구현 산출물 | 종료 조건 |
| --- | --- | --- |
| H0 | 공통 reader/DTO·capabilities·v2 capture/비교 계약; 로컬 adapter | HG03/04/08/10 계약 fixture, 기존 로컬 회귀 및 v1 원본 보존 |
| H1 | 수동 등록·env 참조·고정 endpoint HTTP·제한/캐시·진행/취소 작업 | HG01/02/16~20; 외부 서비스 없이 transport fixture로 경계 검증 |
| H2 | GitHub identity/ref/tree/blob reader | HG05/07/09/11 및 pinned 실제 공개 GitHub 검증 |
| H3 | GitLab identity/ref/tree/raw-blob reader | HG06/07/09/11 및 pinned 실제 공개 GitLab 검증 |
| H4 | 공통 지도·하단 코드/Diff·변경 목록·이력·editor/permalink·offline | HG10/12~15/20~25; source별 의미와 coverage가 화면에서 일치 |
| H5 | 공개/비공개·3 OS·브라우저·패키지·성능·보존 검증서 | HG26~32와 전체 기준의 실제 결과/미검증 한계 공개 |

H0–H4는 기존 공개 GitHub·GitLab reader 검사와 이번 Git 기반 provider 브라우저 fixture를 포함한 macOS 한정 근거와 함께 구현했습니다. H5의 공개·데스크톱 범위 결과와 남은 한계는 [H5 기록](REPOSITORY_HOSTED_H5_KR.md)을 따릅니다. H2/H3의 공개 탐색이 확인된 뒤 같은 계약으로 비공개를 검증합니다. private fixture나 Enterprise·실기기·native editor 근거가 없으면 해당 범위를 NOT_RUN으로 남기고 지원 주장을 제한합니다. 기존 Windows POSIX 전용 검사 제외를 원격 기능 성공으로 해결된 것처럼 바꾸지 않습니다.

## 9. 예상 코드 영향

| 대상 | 변경 범위 |
| --- | --- |
| `providers/base.py`, `providers/local.py` (신규) | reader/DTO와 기존 Local Git adapter; 동적 plugin loader는 추가하지 않음 |
| `providers/github.py`, `providers/gitlab.py` (신규) | 고정 API reader; provider마다 HTML/지도 렌더러를 복제하지 않음 |
| `registrations.py`, `http_reader.py` (신규) | 앱 데이터 등록과 env 참조; bounded HTTP·cache·요청 정책 |
| `capture.py`, `analyze.py` | v1 호환 읽기·v2 보존·공통 snapshot 원문 분석 |
| `compare.py` | revision 쌍·트리 합집합·정확한 원문 Diff |
| `viewer.py`, `cli.py`, `assets/*` | source/capability·비동기 수집 상태·선택 신원·공통 UI |
| `export.py`, `schemas/*`, `tests/*`, 영·한 문서 | provider 없는 offline 재생·origin 분리·fixture·검증 근거 |

## 10. 검증 매트릭스

아래 표는 처음 정한 검증 목표입니다. 완료된 검사와 남아 있는 NOT_RUN 항목은 H0–H5 보고서에서 확인하세요. HG27/28은 실제 provider 검증이며 mock과 구분합니다. HG13의 merge-base 모드는 선택 기능이므로 직접 비교의 정확성은 필수이고 미구현 모드는 숨깁니다. HG24의 로컬 파일 매핑도 제공한 방식만 검증 완료로 표시합니다.

| ID | 단계 | 시나리오 | 관측 가능한 통과 조건 |
| --- | --- | --- | --- |
| HG01 | H1 | 명시적 등록 범위 | 등록한 저장소만 요청하며 계정·조직 전체 조회나 fork·submodule 자동 등록이 없어야 합니다. |
| HG02 | H1 | 저장소 신원과 URL 해석 | provider·API host·고정 저장소 ID로 동명 저장소를 구분하고 GitLab 하위 그룹·이름 변경을 처리하며 ID가 바뀌면 중단합니다. |
| HG03 | H0 | 수집 중 ref 변경과 고정 | 브랜치가 A에서 B로 이동해도 모든 읽기는 고정 A를 사용하며 B는 별도 갱신으로 수집합니다. 브랜치·태그 동명과 annotated tag도 명시적으로 해석합니다. |
| HG04 | H0 | 로컬 호환성과 기존 수집본 보존 | 기존 CLI와 v1 수집·지도 파일을 변경 없이 읽고 원격 수집본에 가짜 worktree·index·Git 디렉터리를 만들지 않습니다. |
| HG05 | H2 | GitHub 트리 잘림 | 재귀 응답이 잘리면 예산 안에서 하위 트리를 읽거나 목록 미완료로 표시하며 1,000개 초과 디렉터리를 Contents 목록으로 완성했다고 보지 않습니다. |
| HG06 | H3 | GitLab 페이지와 없는 경로 | 검증한 다음 링크·커서를 따르고 중복 페이지·루프·예상 메타데이터 부재·예산 종료를 명시합니다. 404를 빈 정상 트리로 바꾸지 않습니다. |
| HG07 | H2-H3 | 원문 blob 바이트 신원 | 독립 로컬 fixture와 원문 바이트·크기·SHA256이 같고 GitHub blob OID를 검증하며 GitLab raw blob으로 비 UTF-8 바이트도 변환 없이 읽습니다. |
| HG08 | H0 | 0바이트·부재·미확보 구분 | 빈 파일에도 실제 해시가 있고 삭제는 완료된 고정 목록으로만 판단합니다. 미수집·접근 거절·과대·손상 원문을 빈 파일로 바꾸지 않습니다. |
| HG09 | H2-H3 | symlink·submodule·LFS 경계 | mode와 LFS pointer를 구분하고 대상 추적·압축 해제·Git filter·프로젝트 import·코드 실행이 없어야 합니다. |
| HG10 | H0-H4 | 로컬·provider 지도 동등성 | 동일 fixture 커밋에서 세 소스의 파일·심볼·문서·호출 관계와 줄·설명·명시적 기능 연결이 정규화 후 같아야 합니다. |
| HG11 | H2-H3 | 경로 인코딩 | 공백·한글·+·%·#·탭/개행·slash ref·서로 다른 Unicode 표기의 신원을 유지하며 표현 불가 바이트 경로는 대체 경로가 아닌 미지원 공백으로 남깁니다. |
| HG12 | H4 | 전체 변경 경로 목록 | 350개 이상 변경 fixture에서도 두 고정 트리로 경로 목록을 만들고 provider compare 누락에 영향받지 않으며 부분 트리는 전체 목록으로 표시하지 않습니다. |
| HG13 | H4 | 직접 비교·merge-base 비교 구분 | 분기 fixture에서 A→B와 merge-base→B 결과를 구분하며 표시와 고정 양 끝 버전이 선택한 모드와 일치해야 합니다. |
| HG14 | H4 | 파일별 정확한 Diff | 추가·삭제·rename 힌트·mode·binary·BOM·CRLF·마지막 개행 차이가 양쪽 경로·커밋·해시와 연결되고 patch 부재를 차이 없음으로 만들지 않습니다. |
| HG15 | H4 | 범위별 완료 상태 | 파일 목록·원문 수집·지원 언어 분석·변경 경로의 수와 완료 상태를 구분하고 정적 연결을 실행·CALF 성공으로 승격하지 않습니다. |
| HG16 | H1 | 인증·접근 실패 | 환경 변수 부재·401·권한/제한 403·비공개 또는 부재인 404·빈 저장소를 구분하고 접근 실패가 기존 수집본을 덮지 않습니다. |
| HG17 | H1 | 자격증명 보존 경계 | 시험 토큰은 지정된 외부 인증 헤더에만 있고 argv·등록 파일·로그·브라우저 데이터/저장소·링크·캐시·내보내기에 없어야 합니다. |
| HG18 | H1 | HTTP 목적지와 endpoint 정책 | 설정된 HTTPS API origin과 읽기 endpoint 틀만 사용하며 악성 다음 링크·redirect·다른 프로젝트 커서·부작용 GET을 거절합니다. |
| HG19 | H1 | 사용량 제한과 조건부 캐시 | provider의 재시도·리셋 시각 전 요청을 반복하지 않고 304는 대응 캐시·인증 구획이 있어야 하며 무한 재시도·오래된 자료의 최신 승격·등록 간 유출이 없어야 합니다. |
| HG20 | H1-H4 | 한도·취소·늦은 응답 | 과대·잘린 응답·DNS/TLS/읽기 정지·취소·역순 응답을 제한하며 취소 작업은 게시하지 않고 늦은 결과가 최신 선택을 덮지 못합니다. |
| HG21 | H4 | 지도와 하단 패널의 일치 | 맵 전체 아래에서 설명·기능·코드 줄·원문 해시·지도 버전이 노드/관계 선택과 일치하며 코드 버전 전환이 지도를 자동으로 바꾸지 않습니다. |
| HG22 | H4 | 탐색 신원과 복원 | 같은 등록·수집·지도 ID에서 이력·고정·줌·언어·ref·Diff 양쪽을 복원하며 다른 소스나 매핑 해시의 링크를 자동으로 재사용하지 않습니다. |
| HG23 | H4 | 원격 버전 기능 표시 | 원격 화면은 선택 커밋과 비교 양쪽을 제공하며 로컬 index·working·stage 조작은 없고 provider 링크는 검증된 저장소와 고정 커밋을 사용합니다. |
| HG24 | H4 | 에디터 대상 신원 | 보존 사본 또는 명시적으로 연결한 일치 로컬 파일만 커밋·blob·줄을 확인해 열며 가짜 로컬 checkout이나 원격 편집 경로를 만들지 않습니다. |
| HG25 | H4 | 오프라인 내보내기 | 네트워크 차단·원본 숨김 상태에서 포함 범위의 지도·코드·Diff가 작동하고 원문·origin은 명시적으로 포함하며 토큰·로컬/에디터 경로는 제외합니다. |
| HG26 | H5 | Local·FFmpeg·CALF 보존 | 영향받는 Local Git·FFmpeg 계약 검사를 수행하고 원래 소스·refs/index/설정·v1 수집본·FFmpeg 릴리즈·CALF 기록의 기준 해시를 보존합니다. |
| HG27 | H5 | 실제 공개 저장소 검증 | 두 provider의 실제 고정 fixture 원문·지도·Diff를 독립 검증하고 API 버전·수·제한을 기록하며 mock만으로 provider 지원을 검증했다고 하지 않습니다. |
| HG28 | H5 | 비공개 provider 검증 | provider별로 명시 승인된 비공개 fixture와 읽기 접근을 검증하고 실제 근거가 없으면 NOT_RUN으로 남겨 공개 지원 주장을 제한합니다. |
| HG29 | H5 | 실제 플랫폼·브라우저 검증 | macOS·Windows·Linux 실제 브라우저에서 영·한 전환·1440/390/320 폭·코드 스크롤·줌/핀치·콘솔 오류를 확인하고 실기기·에디터 실제 실행은 따로 표시합니다. |
| HG30 | H5 | 패키지와 provider 독립성 | 새 패키지 설치에서 자산·스키마·CLI를 확인하고 provider 자격증명·SDK/코어/모델 없이 Local Git이 오프라인 동작하며 다른 팩과 기록을 보존합니다. |
| HG31 | H5 | 측정한 성능과 한도 | 정의한 fixture에서 요청·원문·페이지 예산, cold/cache 시간과 최대 메모리를 기록합니다. 목표는 진행 표시 1초·캐시 열기 2초·취소 정리 10초·최대 RSS 512 MiB 이내입니다. |
| HG32 | H5 | 원격 읽기 효과와 근거 | 요청 기록은 지정 읽기 endpoint뿐이며 원격 쓰기·Git clone/fetch/push·webhook·CI 시작·프로젝트 코드 실행이 없어야 합니다. 미완료·실패·정리 근거도 보존합니다. |

## 11. 독립 근거와 판정

같은 작은 합성 저장소를 Local/GitHub/GitLab에 명시적으로 등록하고, 바이트·Git blob·commit·mode·경로의 기대값은 로컬 Git 및 독립 바이트 해시로 만듭니다. 호출/문서 링크의 기대 줄과 방향은 fixture 사양에서 정하고 구현 출력으로 다시 만들지 않습니다. truncation·잘못된 페이지·만료 토큰·제한 응답·변환된 JSON 원문·느린/역순 응답은 별도 HTTP fixture로 검증합니다.

실제 provider 시험은 등록한 시험 저장소를 읽는 범위만 사용합니다. private 시험용 저장소 생성·새 token 발급·원격 변경을 계획만으로 실행하지 않습니다. 공개 시험과 비공개 시험, API 연결과 전체 UI 성공, 캐시와 실제 네트워크를 구분해 기록합니다.

성능은 cold/cache를 나누고 fixture 규모·지연·요청 수·부분 수집 여부를 함께 기록합니다. 예시 규모는 10,000개 목록 항목과 100개 분석 원문이며, 현 Local Git의 10,000파일/20,000커밋 결과를 원격 성능으로 재사용하지 않습니다. 표의 수치는 목표이며 측정 결과가 아닙니다.

회귀 기준은 현 검증서의 macOS/Debian 22개와 Windows 21개+POSIX 제외 1개입니다. 기존 FFmpeg 검사·release 파일·CALF 기록·owner 설정을 변경하지 않습니다. 변화가 감지되면 이 작업의 쓰기와 다른 동시 작업을 구분하고 임의 복원하지 않습니다. 일부 범위를 못 검증해도 기존 릴리즈를 새로 막는 정책을 만들지 않으며 해당 기능의 지원 주장만 제한합니다.

검증 산출물은 등록/고정 버전 manifest, credential을 제거한 요청 요약, 원문 해시, 범위별 결과, UI 증거와 종료/보존 확인입니다. 새 기록은 predecessor/successor로 추가하고 기존 검증서와 수집본을 성공으로 덮어쓰지 않습니다. CI나 provider 상태를 native CALF 성공/릴리즈 권한으로 바꾸지 않습니다.

