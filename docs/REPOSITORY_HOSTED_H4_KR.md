# H4 공통 소스 선택·지도·코드/Diff

[English](REPOSITORY_HOSTED_H4.md) · [계획](REPOSITORY_HOSTED_PLAN_KR.md) · [검증 기록](verification/repository-hosted-h4-20261107.json)

2026-11-07 · 소스 실행 개발 프리뷰입니다. 수동 등록한 GitHub·GitLab을 기존 지도와 맵 아래 상세 패널에 연결했습니다. Local Git reader, GitHub·GitLab reader, 기존 v1 exporter, FFmpeg 확장과 CALF 기록을 보존합니다. 탐색 기능이 CALF 실행이나 원격 쓰기 권한을 부여하지 않습니다.

## 열기와 수집

기존 `open --repo PROJECT_DIRECTORY --data-dir DATA_DIRECTORY`로 명시한 Local Git worktree 하나를 연결하면, 소스 메뉴에서 수동 등록한 원격 저장소도 선택할 수 있습니다. 원격 소스만 열 수도 있습니다. 데이터·출력 폴더는 조사하는 Git 저장소 밖에 두십시오.

```text
python -m calf_extensions.repository.cli sources add --provider github --url https://github.com/OWNER/REPO --data-dir DATA_DIRECTORY
python -m calf_extensions.repository.cli sources add --provider gitlab --url https://gitlab.com/GROUP/PROJECT --data-dir DATA_DIRECTORY
python -m calf_extensions.repository.cli scan --source SOURCE_ID --ref-kind branch --ref main --data-dir DATA_DIRECTORY
python -m calf_extensions.repository.cli open --source SOURCE_ID --data-dir DATA_DIRECTORY
```

화면에서 저장소 등록·신원 확인·소스 선택 후 branch/tag/전체 commit을 명시해 수집합니다. 선택적인 인증 입력에는 토큰 대신 **환경 변수 이름**만 받습니다. H1 인증·HTTP 정책은 그대로입니다. 계정 전체 탐색이나 자동 clone/fetch/checkout은 하지 않습니다.

`open --source ... --ref-kind branch --ref main`은 소유한 수집 작업을 시작합니다. `scan --source`에는 ref 종류와 이름이 필수이며 부분 수집은 종료 코드 3입니다. `open --view CONTEXT_ID --data-dir DATA_DIRECTORY`는 Git·provider 읽기 없이 보존본을 엽니다. `Ctrl+C`로 포털과 소유 worker를 정지합니다. 원격 전용 포털에 가짜 Local Git 소스를 만들지 않습니다.

## 하나의 지도와 하단 상세

활성 지도는 분석한 **오른쪽 snapshot**에 속합니다. 노드·관계를 선택하면 맵 전체 아래에 설명, 명시적 기능 연결, 원문 신원과 코드를 보여줍니다. 원격 코드 버전은 분석한 오른쪽·비교 왼쪽·비교 오른쪽입니다. 코드 버전을 바꿔도 지도를 다시 분석하거나 자동으로 바꾸지 않습니다. Local Git의 HEAD/index/working/충돌 stage 동작은 유지합니다.

기본 왼쪽은 선택한 오른쪽 commit의 첫 부모입니다. 부모가 없다는 메타데이터를 확인한 경우에만 빈 시작 상태와 비교하며 가짜 commit을 만들지 않습니다. 다른 쌍은 왼쪽 ref 종류와 이름을 지정합니다. 양쪽 ref를 고정한 뒤 목록과 원문을 읽습니다. 비교는 `DIRECT_SNAPSHOT`이며 merge-base 비교는 제공하지 않습니다.

변경 경로는 두 고정 목록의 합집합으로 계산하며 provider patch/compare 한도와 무관합니다. 100개씩 페이지를 넘깁니다. 추가·삭제·수정·mode 변경·목록 미확인을 구분합니다. 유일하게 같은 blob인 경로는 힌트일 뿐이며 추가·삭제를 확정 rename으로 바꾸지 않습니다. 삭제 파일은 현재 오른쪽 지도에 없는 비교 전용 항목으로 하단 패널에서 엽니다. 미수집·binary·지원하지 않는 바이트를 빈 코드나 성공한 빈 Diff로 표시하지 않습니다.

파일 목록, 보존한 일반 파일 원문, Python 분석, 변경 경로, 텍스트 비교 가능 변경을 각각 집계합니다. 수집 `COMPLETE`는 전체 목록과 일반 파일 원문 보존을 뜻하며 모든 언어 분석·텍스트 Diff·런타임·CALF 성공을 뜻하지 않습니다. 응답·보존·내보내기에는 한도가 있으며 큰 Diff는 신원을 유지한 채 `PARTIAL`일 수 있습니다.

## 소스 선택·이력·취소

기존 지도를 사용하는 동안 별도 소유 작업으로 수집하며 단계·요청·파일·원문 확보 수를 표시합니다. 취소하거나 다른 소스를 선택하면 이전 작업은 게시하지 못합니다. 수집 실패 시 기존 활성 지도를 유지합니다. 부분 수집본은 보존 지도에서 명시적으로 열어야 하며 정상 지도를 자동 교체하지 않습니다.

별도 app data의 v2 snapshot·view는 새 파일로만 보존합니다. 이력에 context·snapshot·navigation·ref·비교 신원을 기록하며 같은 소스의 갱신에는 predecessor를 남깁니다. 보존 소스 선택에는 네트워크가 필요 없습니다. 등록을 비활성화해도 보존 지도는 유지하며 새 수집은 거부합니다. 취소 확인 전에 쓴 불변 snapshot/cache 입력이 인덱스 없이 남을 수 있으나 활성 지도로 게시하지는 못합니다.

탐색 링크는 소스·context·capture·navigation·비교 snapshot과 선택·줄·탐색 위치·고정·카메라·코드 높이·언어를 함께 묶고 다른 신원은 거부합니다. API context 확인과 화면 요청 세대로 늦은 코드·Diff가 다른 소스의 화면을 덮지 못하게 합니다.

## Provider 링크와 에디터 사본

Provider 파일 링크는 확인한 저장소 URL과 고정 commit을 사용합니다. 원격에는 local working/index/stage 조작이 없습니다. “보존 코드 사본 준비”는 app data에 안전한 이름으로 해시를 대조한 별도 사본을 만들고 VS Code URI를 제공합니다. 이 사본을 편집해도 수집 바이트나 provider는 바뀌지 않습니다. H4에서는 외부 에디터 실행을 검증하지 않았고 자동 실행하지 않습니다. 기존 Local Git 에디터 링크는 유지합니다.

## v2 오프라인 내보내기

```text
python -m calf_extensions.repository.cli export --data-dir DATA_DIRECTORY --view CONTEXT_ID --output NEW_OUTPUT_DIRECTORY
python -m calf_extensions.repository.cli export --data-dir DATA_DIRECTORY --view CONTEXT_ID --output NEW_OUTPUT_DIRECTORY --include-source
```

원문과 원시 바이트는 `--include-source`로 명시적으로 포함합니다. 원본 URL·저장소 신원·ref 이름은 별도 `--include-origin` 옵션입니다. 기본값은 불투명한 소스 신원과 commit ID를 쓰며 에디터·로컬 경로와 인증 참조를 제외하고 에디터 기능을 숨깁니다. 파일명·설명·사용자 정의를 포함한 프로젝트 본문은 지도 내용으로 남습니다. 본문에 들어간 비밀까지 자동 제거하지 않으므로 공유 전에 내용을 확인하십시오.

포함한 원시 바이트는 Base64·SHA256 근거를 유지합니다. 원본 저장소를 숨기고 HTTP를 막아도 포함한 코드·Diff를 탐색합니다. manifest는 보존 완료와 한도로 제한한 내보내기 범위를 구분하며 제외 원문은 미확보로 남습니다. 출력은 저장소·app data 밖의 새 폴더여야 합니다. 기존 `--capture` 내보내기는 그대로입니다.

## 검증 범위와 남은 단계

macOS에서 repository 시험 121개, 최종 버전 거부 보강 뒤 H4 집중 검사 20개, FFmpeg 계약 3개, 실제 Chrome 원격 fixture 포털·오프라인과 보존된 독립 Local Git/v1 브라우저 회귀를 확인했습니다. 원격 화면 검증은 독립적으로 만든 실제 Git 객체에서 provider 응답을 구성하고 변경하지 않은 GitHub·GitLab reader를 통과시켰습니다. **이번 실행에서는 실제 원격 서비스나 비공개 계정을 검증하지 않았습니다.** H2/H3 공개 reader 근거는 수정 없이 역사 기록으로 유지합니다.

Chrome에서 맵 아래 코드·Diff, 호출 줄 6, 고정 provider 링크, 에디터 사본 URI, 비교 양쪽 원문, 늦은 응답 격리, 탐색 링크·언어·높이 복원, script canary 비실행과 1440/390/320 폭을 확인했습니다. 오프라인은 원본 숨김·HTTP 차단 상태입니다. 검증 뒤 소유 서버 socket·worker·브라우저를 정리합니다.

H5의 비공개 provider 권한, 전체 실제 provider 행렬, Windows/Linux 원격 UI, 실제 모바일 기기, 외부 에디터 실행, 새 패키지 설치와 성능·최대 메모리 측정은 남습니다. 전체 행렬 HG01–HG32는 NOT_RUN으로 유지하며 H4 한정 진척을 별도로 기록합니다. 커밋·push·패키지 게시를 포함하지 않습니다.

