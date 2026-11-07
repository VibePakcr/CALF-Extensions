> 하위 Git 출처·버전 계층의 기술 참고입니다. 제품 화면과 구현 우선순위는 [프로젝트 지도 계획](REPOSITORY_LOCAL_GIT_PLAN_KR.md)을 따릅니다. 아래의 기존 Git 중심 단계는 독립 제품 계획이 아닙니다.

# CALF Repository Navigator Local Git 구현 계획

[English](REPOSITORY_LOCAL_GIT_PLAN.md) · [CALF Extensions](../README_KR.md)

상태: 구현 전 계획. 이 문서의 기능과 검증 항목은 Local Git 확장의 구현·수락 기준이며, 현재 배포된 FFmpeg 확장의 지원 목록에 추가된 기능이 아닙니다.

CALF Extensions에 무료 저장소 탐색 확장을 추가합니다. 첫 목표는 개발자가 로컬 저장소 하나를 열고 구조·변경·이력을 살펴본 뒤, 선택한 파일의 정확한 버전과 줄을 코드·Diff·에디터에서 이어서 확인하는 것입니다. 기본 탐색은 Python 3.10 이상, 설치된 Git, 브라우저로 동작하며 CALF 코어·SDK·계정·AI API를 요구하지 않습니다. CALF 근거 연결과 GitHub·GitLab 서비스 API는 후속 단계입니다.

## 1. 첫 구현 범위

| 포함 | 구체적인 동작 |
| --- | --- |
| 저장소 확인 | 일반 저장소·linked worktree·detached HEAD·첫 커밋 전 상태를 구분합니다. Git 실제 경로·버전·object format·worktree와 공통 Git 디렉터리를 관측합니다. |
| 파일 탐색 | 현재 추적 파일 트리, 경로 검색, 변경 상태 필터, 선택한 커밋의 트리를 제공합니다. untracked는 사용자가 포함할 때만 수집하며 ignored는 제외합니다. |
| 커밋과 이력 | 커밋 부모 관계, 선택 커밋의 파일 변경, 페이지 단위 이력, 파일별 이력과 rename 후보를 제공합니다. merge는 비교 부모를 명시합니다. |
| 변경 구분 | HEAD→index, index→작업 파일, HEAD→작업 파일, 명시한 두 커밋의 비교를 각각 제공합니다. 충돌 단계는 정상 staged 파일과 분리합니다. |
| 맵과 상세 패널 | 커밋→부모·커밋→변경 파일·디렉터리→파일 관계를 탐색합니다. 맵 아래에 파일 정보·원문·Diff·버전·줄 이동·에디터 링크를 둡니다. |
| 탐색 조작 | 확대·이동·맞춤, 로드된 범위의 연결 단계, 뒤로/앞으로, 파일 고정 비교, 패널 접기·높이 조절, 버전에 결합된 탐색 링크를 제공합니다. |
| 로컬 뷰어 | 사용자가 연 동안만 foreground loopback 서버를 실행해 선택한 파일을 필요할 때 읽습니다. 종료 시 자식 프로세스·포트·임시 자료를 정리합니다. |
| 보존·내보내기 | 별도 앱 데이터 영역에 JSON 색인과 원문 수집본을 보존합니다. 새 폴더에 오프라인 HTML·JSON을 내보내며 원문 포함은 선택 사항입니다. |
| 설명과 언어 | HEAD·index·작업 파일·merge 부모·수집본 등 용어를 설명합니다. 영·한 토글은 선택 언어의 UI 문구만 표시합니다. 사용자 코드·커밋 메시지는 번역하지 않습니다. |

Git이 제공하지 않는 함수 호출·import·runtime 관계는 이번 범위에서 추정하지 않습니다. 첫 맵의 관계 유형을 화면에 명시하고, 기존 VibePackr의 보존 GAPE 그래프를 범용 분석 결과로 재사용하지 않습니다. 언어별 분석기는 후속 확장입니다. 파일의 역할 설명은 확인된 문서·주석·사용자 연결 자료에 출처를 붙이고, 연결되지 않은 설명은 미등록으로 표시합니다.

Bare repository와 promisor/partial clone은 첫 버전에서 감지 후 명시적으로 미지원 처리합니다. Shallow clone은 현재 접근 가능한 이력과 shallow 경계를 표시합니다. Submodule은 gitlink와 대상 commit ID만 보여주며 재귀 진입하지 않습니다. Git LFS 포인터는 포인터로 표시하고 payload를 받지 않습니다.

## 2. 저장소와 버전의 신원

Git에는 모든 clone에 공통인 고유 저장소 ID가 없습니다. 확장 프로젝트의 `repository_id`를 앱 데이터에 생성하고, 다른 clone·경로의 연결은 명시적으로 재등록합니다. Remote URL이나 브랜치 이름만으로 같은 저장소·버전이라고 판단하지 않습니다.

| 데이터 | 식별·표시 계약 |
| --- | --- |
| Repository | 확장 UUID, 관측한 물리 root·Git common directory·object format. 이 경로들은 로컬 관측이며 공유용 정본 ID가 아닙니다. |
| Worktree | 별도 `worktree_id`, private Git directory, root, HEAD OID 또는 unborn, branch 또는 detached. 다른 worktree의 index와 섞지 않습니다. |
| Commit file | repository ID + 전체 commit OID + 원래 path + blob OID·mode. OID 길이 40자를 고정하지 않습니다. |
| Index file | stage 번호 0/1/2/3, blob OID·mode, index 관측 digest. intent-to-add·삭제·충돌을 구분합니다. |
| Working file | 물리 경계 안의 일반 파일에 대한 별도 수집 ID, 바이트 SHA256, 크기·수집 시각·표시 인코딩. 아직 읽지 않은 파일은 SHA 미확인입니다. |
| Comparison | left/right의 종류·commit/blob/capture ID·path, merge 부모 번호, rename 탐지 설정, diff 형식·범위. |
| Graph edge | 유형·양 끝 ID·출처·분석 버전·대상 범위. Commit과 파일의 관계를 함수 호출로 바꾸지 않습니다. |
| Coverage | 요청한 refs·경로·이력 범위, 수집 수, 제외·미지원·잘림 이유, 다음 페이지와 boundary. |

Rename은 명시한 Git 유사도 기준 50%의 관측 결과입니다. 원래 path·OID를 보존하고, 복사·rename 후보를 영구적인 파일 동일성으로 승격하지 않습니다. 여러 부모 merge는 기본 1번 부모를 명시하고 다른 부모를 선택할 수 있게 합니다. 파일 이력은 우선 HEAD 기준이며, rename 추적·shallow·merge 경계를 함께 표시합니다.

JSON 색인은 `schema`, `extension_version`, `git_version`, `repository`, `worktree`, `capture`, `nodes`, `edges`, `comparisons`, `coverage`를 분리합니다. 날짜·소유자·설명과 기계 ID를 혼합하지 않습니다. 파일 경로는 원래 표현을 복구할 수 있도록 보존하며, 디코딩할 수 없는 경로는 escaped 표시와 제한 이유를 제공합니다.

## 3. 수집과 갱신 계약

소스·Git refs·index·설정·원래 CALF 기록을 변경하지 않습니다. 확장의 출력·캐시·임시 파일은 선택한 worktree와 모든 관련 Git 디렉터리 밖에 둡니다. 기본 위치는 플랫폼별 앱 데이터이며 `--data-dir` 또는 `CALF_REPO_HOME`으로 바꿀 수 있습니다. 개발·검증 환경에서는 T9 경로를 명시합니다. 기존 `CALF_HOME`이나 CALF 기록 위치를 추측해 사용하지 않습니다.

Git은 확인한 실행 파일의 argv 배열로 호출합니다. `shell=False`, pager·색상·optional index writes·fsmonitor·external diff·textconv를 끄고, NUL 구분 경로·길이가 있는 blob 읽기·literal path 처리를 사용합니다. 저장소의 hook·필터·명령을 실행하지 않습니다. Diff는 raw blob/index/수집 바이트에 기반하며 Git의 속성 변환을 원문과 혼동하지 않습니다. Commit/path 입력은 고정된 읽기 명령의 검증된 데이터로만 전달합니다.

Git 상태와 raw 바이트 차이는 별도입니다. 정상적인 CRLF checkout은 Git clean 상태에서도 blob과 바이트가 다를 수 있습니다. `status`·working-tree diff도 attribute의 clean/process 필터를 실행할 수 있으므로 단순히 읽기 명령으로 간주하지 않습니다. P0에서 effective filter·attribute·submodule 경로까지 sentinel로 확인하고, 외부 실행을 막는 설정을 검증한 명령만 허용합니다. 필터를 실행하지 않아 Git과 동일한 상태를 판정할 수 없는 파일은 `status_basis=RAW_BYTES`와 이유를 표시합니다. 알려지지 않은 상태를 clean으로 채우거나 raw 차이만으로 Git dirty라고 단정하지 않습니다. 누적 상태도 관측 범위·미확인 수를 포함합니다. `safe.directory` 등 신뢰 설정을 자동 변경하지 않습니다.

첫 discovery 단계에서 지원 Git 버전·명령·환경 옵션의 실제 계약을 확인하고 최소 버전을 문서화합니다. 현재 개발 호스트의 Git 2.54.0 관측은 모든 지원 플랫폼의 최소 버전 증거가 아닙니다. Promisor 설정·누락 object를 감지하고 자동 fetch가 발생할 경로를 차단합니다. Fetch·clone·checkout·add·commit·push·설정 변경·도구 설치는 탐색 API가 제공하지 않습니다.

메타데이터 수집 전후 HEAD·refs·stage 목록을 대조합니다. 바뀌면 일관된 완료본으로 발행하지 않고 `SOURCE_CHANGED`로 남깁니다. 작업 파일은 열 때마다 안정된 일반 파일 읽기와 SHA를 확보해 독립 수집본으로 저장합니다. 디렉터리 전체의 atomic snapshot이라고 부르지 않습니다. 오래된 수집본을 열면 수집 시각을 표시하고, 현재 파일이 달라졌다면 별도의 상태로 보여줍니다.

수집본은 새 ID에 create-only로 발행합니다. 중단·부분 성공·불완전 수집이 마지막 완전 수집본을 덮지 않습니다. 자동 재시도하지 않으며 최초 오류와 cleanup 결과를 각각 남깁니다. 명시적 새로고침은 새 수집을 만듭니다. 파일 감시 서비스는 첫 버전에 추가하지 않습니다.

텍스트는 UTF-8과 UTF-8 BOM을 우선 지원합니다. 원래 바이트·개행·마지막 개행의 유무를 보존하며 `errors=replace`로 원문을 만들어내지 않습니다. Binary·다른 인코딩·oversized·누락 object·symlink는 종류와 이유를 표시합니다. Git의 symlink blob은 링크 문자열로 볼 수 있지만 작업 파일의 링크 대상은 따라가지 않습니다. 충돌 파일을 성공적으로 병합된 파일로 표현하지 않습니다.

## 4. 화면과 실행 흐름

1. `open`이 repository와 data directory를 확인하고 가벼운 화면을 먼저 엽니다. 프로젝트 요약에 HEAD·branch·dirty 상태·관측 시각·수집 범위를 표시합니다.
2. 상단 공통 메뉴에서 파일·변경·이력·맵·내보내기로 이동합니다. 검색과 필터의 적용 범위를 각각 명시합니다.
3. 파일을 선택하면 맵 아래 패널에 버전 선택, SHA/OID, 줄번호 원문, 비교 기준, Diff, 파일 이력과 에디터 링크가 표시됩니다.
4. 커밋·관계를 선택하면 해당 부모·변경 파일·정확한 원문으로 이동합니다. 선택과 종류가 맞지 않는 URL 상태는 거절하거나 해제합니다.
5. 탐색 이력은 선택·비교·필터·단계·고정 파일·코드 줄·화면 중심·확대율을 함께 복원합니다. 새 hash 이동도 초기 진입과 같은 계약으로 처리합니다.
6. 에디터 열기는 사용자가 누를 때 동작합니다. 현재 작업 파일과 보존 사본의 대상을 구분하고, 지원되는 에디터 URI와 경로·줄 복사 fallback을 제공합니다.
7. 종료하면 로컬 뷰어만 정리합니다. 보존 수집본은 남깁니다.

공간은 디렉터리→파일→커밋 관계로 단계적으로 확장합니다. 로드한 200개 커밋을 전체 이력이라고 표시하지 않습니다. 표시 수·수집 수·추가 페이지·제외 수를 구분합니다. 큰 목록과 코드는 페이지/구간 단위로 렌더링합니다. 기본 이력 페이지는 200개, 코드 창은 200줄입니다.

로컬 서버는 `127.0.0.1`의 임의 포트에만 바인딩하고 실행별 접근 토큰·Host/Origin 검사를 둡니다. 임의 filesystem 서버나 명령 실행 서버를 만들지 않습니다. 등록된 repository ID와 검증된 상대 경로·OID만 요청할 수 있으며, 외부 origin·경로 탈출·원격 바인딩을 거절합니다. CORS wildcard·CDN·외부 스크립트 없이 동작하고 로그·내보내기에 접근 토큰을 쓰지 않습니다. 소스·커밋 메시지·파일명은 실행하지 않는 데이터입니다.

아래는 제안 CLI이며 아직 구현된 명령이 아닙니다.

```text
calf-repo open --repo PATH [--data-dir PATH] [--git PATH]
calf-repo scan --repo PATH --data-dir PATH
calf-repo export --data-dir PATH --capture ID --output NEW_DIRECTORY [--include-source]
```

`scan/export`는 stdout에 UTF-8 JSON 응답 하나를 쓰고 진행·진단은 제한된 stderr로 분리합니다. `open`은 token 없는 READY 응답 후 foreground로 유지하며 정상 종료 코드가 원문 수집 성공을 뜻하지 않습니다. 확장의 수집 상태는 CALF의 `SATISFIED/UNKNOWN/VIOLATED`를 대신 사용하지 않습니다.

| 종료 코드 | 의미 |
| --- | --- |
| 0 | 선언한 범위의 scan/export 완료 또는 viewer 정상 종료 |
| 1 | 실행·입력·cleanup 실패 |
| 2 | CLI 문법 오류 |
| 3 | 한도 등에 따른 부분 결과; coverage/reason 필수 |
| 4 | 미지원 저장소·도구 capability |
| 5 | 수집 중 source 변경; 완료본 발행 안 함 |
| 130 | 취소와 소유 자원 cleanup 확인. Cleanup 실패면 코드 1과 두 결과를 보존 |

`scan`은 JSON 색인만 생성하고 브라우저를 열지 않습니다. `export`는 지정 수집본만 사용하며 원문을 새로 읽거나 Git을 갱신하지 않습니다. 원문 미포함이 기본이고, 포함 시 선택·수집된 원문의 범위와 제외 수를 미리 보여줍니다. Export에는 SDK 기록·인증정보·Git 설정·절대 root·에디터 로컬 경로를 기본 포함하지 않습니다. 공유본에서 로컬 에디터 연결은 별도 경로 매핑이 필요합니다.

## 5. 구현 구조와 기존 자산 재사용

```text
calf_extensions/repository/
  cli.py                 open / scan / export
  git_reader.py          제한된 Git 읽기와 subprocess 수명
  model.py               저장소·버전·관계·coverage 계약
  capture.py             안정성 검사와 create-only 수집
  compare.py             HEAD/index/작업 파일 및 commit 비교
  viewer.py              foreground loopback 읽기 API
  export.py              오프라인 JSON·HTML 생성
  assets/                범용 HTML·CSS·JS·영한 UI 문구
  schemas/               색인·수집·비교 계약
  tests/                 단위·실제 Git fixture 검증
```

기존 소스맵에서 맵 조작·하단 inspector·코드/차이 표현·이력·상태 링크를 추립니다. VibePackr 경로·제품 코드·수집 원문·GAPE 데이터·T9 정책을 배포 자산에 복제하지 않습니다. 새 CLI는 `calf-media`와 분리하며 기본 실행에서 `calf_sdk`를 import하지 않습니다. Runtime 제3자 Python/Node 의존성과 FFmpeg 요구를 추가하지 않습니다. Git과 브라우저는 사용자의 설치본을 사용합니다.

배포 시 entry point·package-data·영·한 사용법·독립적인 repository 검증 요약을 추가합니다. 기존 FFmpeg 검증서·체크섬·릴리즈 기록을 새 확장의 성공 근거로 재사용하지 않습니다. 현재 core/SDK/라이선스 파일을 수정하거나 동봉하지 않습니다. 무료 확장 라이선스 경계를 유지합니다.

## 6. 구현 순서와 단계별 종료 조건

| 단계 | 구현 산출물 | 다음 단계로 넘어가는 조건 |
| --- | --- | --- |
| P0 계약 확인 | Git capability matrix, 읽기 명령 목록, 데이터 schema, CLI 실패/부분 성공 계약, loopback 수명 설계 | 일반·worktree·unborn·detached·shallow·partial·bare 분류 fixture와 네트워크/외부 프로그램 비실행 관측 확보 |
| P1 Git 수집 | repository/worktree 신원, tree·stage·status·commit 부모·경계·페이지 수집, JSON | LG01–LG06·LG09–LG11·LG14–LG17·LG20의 수집 기준 통과 |
| P2 원문·비교 | blob/index/작업 파일 수집, 4종 비교, 충돌·rename·merge·binary 상태 | LG07–LG13·LG17·LG19·LG20 통과; 원문 SHA와 Diff 재구성 대조 |
| P3 뷰어 | 실제 로컬 읽기 API, 맵 하단 inspector, 언어 토글·검색·이력·에디터 | LG18·LG21–LG24·LG26 UI/API 기준 통과; 원본 모드별 표시 대조 |
| P4 내보내기 | 새 수집본 기반 offline HTML/JSON, 범위·원문 선택, 휴대용 경로 | LG14·LG17·LG19·LG21·LG25 통과; 네트워크 차단 상태에서 재열기 |
| P5 배포 준비 | 3 OS 실제 실행 기록, 설치·package-data·영·한 문서, regression 보고 | LG01–LG28의 해당 플랫폼 항목 통과; 기존 media 검증과 격리·보존 확인 |

단계 산출물은 후속 단계의 입력입니다. 검사·API 구조를 먼저 고정하고 UI와 수집기가 각자 다른 버전 의미를 만들지 않도록 합니다. Packaging·공개 게시·원격 push는 별도 실행 단계이며 이 계획 작성에 포함하지 않습니다.

## 7. 검증 기준

시험은 새 임시 Git 저장소·별도 앱 데이터·명시적 Git 실행 파일에서 수행합니다. 고정된 파일 바이트·커밋 구성·기대 stage와 부모 관계를 먼저 정의하고, 독립 Git 조회·직접 파일 SHA·브라우저 표시를 대조합니다. 수집기의 자체 출력만 기대값으로 삼지 않습니다. 모든 항목은 구현 후 실행할 수락 기준입니다.

| ID | 시험 대상 | 합격 조건 |
| --- | --- | --- |
| LG01 | Clean repository | refs·HEAD·tree·tracked 파일·blob/mode가 독립 Git 조회와 일치하고 dirty를 만들지 않음 |
| LG02 | Worktree 두 개 | 같은 common directory와 각 private index·HEAD를 구분하며 서로의 변경을 섞지 않음 |
| LG03 | Unborn·detached | 첫 커밋 전을 빈 실패나 가짜 HEAD로 표현하지 않고 detached도 정확한 OID로 탐색 |
| LG04 | Branch·tag·refresh | ref 이동 전후를 다른 관측으로 보존하고 이전 링크는 원래 OID 유지 |
| LG05 | Commit DAG·merge | 양쪽 부모를 보존; 부모별 Diff가 선택한 Git 비교와 일치; root commit의 빈 tree 비교도 정확 |
| LG06 | Shallow·범위·pagination | shallow 경계·다음 페이지·요청한 범위를 표시; 누락 없이 페이지 결합; 무한 전체 이력 주장 없음 |
| LG07 | Staged·unstaged 동시 변경 | 한 파일의 HEAD A·index B·작업 파일 C를 세 버전으로 유지; 세 가지 비교가 각 정확한 바이트에 대응 |
| LG08 | Create·delete·mode·rename | 추가/삭제/실행권한·intent-to-add·rename 후보를 구분; rename 설정/원래 path 보존 |
| LG09 | 충돌 index | stage 1/2/3·작업 파일을 구분하고 병합 성공·staged 완료로 표시하지 않음 |
| LG10 | 경로 | 공백·한글·대소문자·탭·개행·선행 하이픈을 유실/명령 해석하지 않음; OS가 만들 수 없는 이름은 명시적 N/A |
| LG11 | SHA object format | 지원 Git에서 SHA-1·SHA-256 실제 fixture 통과; 40자 가정 없음; 미지원 도구는 최소 버전 계약대로 거절 |
| LG12 | Text·개행 | UTF-8/BOM·CRLF/LF·마지막 개행 차이를 보존; 코드 줄·SHA 일치; Diff로 재구성한 text와 대상 일치, 개행 바이트 차이는 별도 표시 |
| LG13 | Non-text·링크 | binary·비UTF8·oversized·LFS pointer·symlink·submodule에 명시 상태; 링크/payload를 자동으로 읽거나 받지 않음 |
| LG14 | No mutation | 실행 전후 refs·index 바이트·tracked/선택 untracked·설정/attribute/hook hash가 같고 검사 대상 안에 새 출력이 없음 |
| LG15 | No implicit execution/network | sentinel hook·fsmonitor·ext-diff·textconv·clean/process 필터·credential helper 호출 0, 원격 접속 0; malicious 파일명/메시지는 데이터로만 표시 |
| LG16 | Unsupported·누락 | partial/promisor·bare·invalid repo·누락 object를 명시 분류; clone/fetch/자동 복구·가짜 빈 성공 없음 |
| LG17 | 수집 중 변경·부분 성공 | HEAD/index/파일 변경 주입 시 완료본 발행을 막고 최초 오류 보존; 이전 완전본 유지; 개별 파일 수집 시각 구분 |
| LG18 | Foreground 서버 | loopback만 listen; 잘못된 token·Host·Origin·ID·경로 거절; 조회 API에 쓰기/명령 실행 경로 없음 |
| LG19 | Timeout·cancel·limits | 작업별 시간/출력/원문 한도 작동; 취소 후 5초 안에 소유 프로세스·포트 정리; cleanup 실패와 최초 실패를 분리 |
| LG20 | Comparison 신원 | 파일·node·edge·버전이 불일치하는 요청 거절; stale 원문에 현재 검증/현재 줄 위치 표시 금지 |
| LG21 | Code·Diff·offline | 화면의 코드 줄과 원문 바이트·Diff 기준이 일치; offline export는 원본 저장소 없이 열리고 누락 코드를 생성하지 않음 |
| LG22 | 탐색 상태·접근성 | 최초/동일 문서 hash·이전/다음·pin·filter·zoom/center 복원; 키보드 초점 유지; 원문과 UI의 언어 경계 유지 |
| LG23 | Editor | URI/경로·줄 검증 및 지원 플랫폼에서 실제 열기 확인; 현재 파일과 수집 사본 분리; export에 원래 절대경로 노출 안 함 |
| LG24 | 화면 크기·언어 | 데스크톱 1440, 모바일 390·320px에서 페이지 가로 넘침 없음; 코드만 독립 스크롤; EN/KO UI 혼합·깨진 문자·console 오류 없음 |
| LG25 | 내보내기 범위 | 새 출력 폴더만 생성; source 미포함 기본·선택 포함·제외 수 정확; 인증·Git 설정·SDK 기록·절대 root·접근 토큰 제외 |
| LG26 | 성능·대형 저장소 | 10,000 tracked 파일·20,000 작은 commit의 고정 fixture, 이력 첫 200개로 각 플랫폼 관측; 아래 응답/메모리 기준 충족 |
| LG27 | Package·regression | 새 폴더 설치에서 assets/영·한 문서/CLI 존재; SDK/FFmpeg 없는 환경에서 Git 탐색 동작; 기존 media 검사와 패키지 기능 유지 |
| LG28 | 실제 플랫폼 근거 | macOS ARM64·Windows x64·Linux x64의 실제 Git/브라우저 실행 결과·버전·artifact hash 보존; 합성/모의 실행을 실제 플랫폼 근거로 승격하지 않음 |

LG26의 초기 목표는 로컬 SSD·동일 fixture에서 화면 shell 1초, 첫 metadata 페이지 10초, 1 MiB 이하 수집 텍스트의 warm open 1초, warm Diff 2초 이내입니다. 브라우저 기본 렌더링은 한 번에 최대 500개 map node와 200줄 코드, 브라우저를 제외한 확장 process tree(Python viewer와 소유 Git 자식)의 peak RSS 512 MiB 이내를 목표로 합니다. 비교 가능한 반복 5회의 최대값과 조건을 보고합니다. 조절해야 하면 원인·측정값·변경 이유를 남기며, 구현이 실패했다는 이유로 목표를 낮추지 않습니다.

초기 자원 한도는 Git 명령 30초, 전체 metadata 수집 120초, stdout 16 MiB·stderr 256 KiB/명령, 원문 preview 1 MiB/파일, export 원문 총 64 MiB입니다. 원문·목록 한도에 걸리면 제외 수/부분 범위를 보여주고 사용자가 더 좁은 범위로 다시 요청하게 합니다. 이력 페이지와 화면 node 제한은 전체 데이터의 삭제가 아니라 명시적인 로딩 범위입니다.

## 8. 수락과 후속 연결

Local Git preview 수락은 위 검증·원본 보존·실제 UI 확인과 영·한 문서 일치를 모두 요구합니다. 테스트 실행 전의 항목은 PLANNED, 미실행은 NOT_RUN, 실패는 FAIL, OS 특성상 불가능한 fixture는 이유가 있는 N/A로 남깁니다. 한 OS의 PASS를 다른 OS에 복사하지 않습니다. Safari/Chromium 계열별 실제 확인 범위도 따로 기록합니다. CALF가 구현 검사를 감독할 경우 새 계약의 현재 입력에 대한 공식 native 판정을 별도 보존하며 프로세스 종료 코드만으로 완료를 판정하지 않습니다.

다음 단계의 CALF 연결은 공식 SDK 0.2.1의 `tasks/inspect/changes`를 통해 출처와 버전을 연결합니다. 현재 작업 목록은 최근 32건이며, `changes`의 task/attempt/recovery는 작업 트리 Git Diff와 구분됩니다. 저장소 탐색은 이 한계를 우회해 core journal/SQLite를 읽거나 CI 성공을 CALF 성공으로 바꾸지 않습니다. GitHub·GitLab은 같은 저장소 모델 위의 PR/MR/CI adapter로 추가합니다.

