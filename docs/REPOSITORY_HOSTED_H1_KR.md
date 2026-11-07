# H1 저장소 등록·인증 참조·HTTP·취소

[English](REPOSITORY_HOSTED_H1.md) · [연동 계획](REPOSITORY_HOSTED_PLAN_KR.md) · [검증 기록](verification/repository-hosted-h1-20261107.json)

2026-11-07 · H1 구현 · macOS 합성 transport 및 기존 Local UI 회귀 검증

H1은 GitHub.com·GitLab.com 저장소 수동 등록과 명시적인 저장소 신원 확인을 제공합니다. 등록은 로컬 작업입니다. provider 접속·자격증명 조회·계정 전체 열람·코드 수집을 시작하지 않습니다. 신원 확인 성공 시 provider의 고정 저장소 ID를 연결합니다. 코드 전체 접근·최신 지도·릴리즈 검증 성공을 의미하지 않습니다. 원격 ref/tree/blob 수집기와 공통 소스 선택 UI는 H2–H4 범위입니다.

## 등록과 확인

설치한 확장 또는 Python import 경로에 패키지가 있는 체크아웃에서 실행합니다. 앱 데이터는 소스 저장소 및 기존 CALF 기록 밖에 둡니다. 아래 대문자 자리표시자를 바꿉니다. 인증 인수에는 서버 환경에 이미 제공한 환경 변수의 **이름**을 쓰며 토큰 값을 쓰지 않습니다.

```text
python -m calf_extensions.repository.cli sources add --provider github --url https://github.com/OWNER/REPO --credential-env MY_GH_TOKEN --data-dir APP_DATA
python -m calf_extensions.repository.cli sources add --provider gitlab --url https://gitlab.com/GROUP/SUBGROUP/PROJECT --credential-env MY_GL_TOKEN --data-dir APP_DATA
python -m calf_extensions.repository.cli sources list --data-dir APP_DATA
python -m calf_extensions.repository.cli sources check SOURCE_ID --data-dir APP_DATA
python -m calf_extensions.repository.cli probe --source SOURCE_ID --data-dir APP_DATA
python -m calf_extensions.repository.cli sources remove SOURCE_ID --data-dir APP_DATA
```

익명 접근은 `--credential-env`를 생략합니다. `sources check`와 `probe --source`는 같은 포그라운드 신원 확인입니다. Ctrl+C는 취소를 요청하고 소유한 작업을 정리합니다. 성공 시 종료 코드 0, 취소 시 130, 실패 시 0이 아닌 종료 코드를 반환합니다. 기존 `open/scan/probe --repo`와 v1 내보내기 인터페이스를 유지합니다. `open/scan --source`는 아직 구현하지 않았습니다.

등록부는 `APP_DATA/registrations`만 관리하며 schema 표식을 검증하고 Git 저장소 내부 출력 위치를 거절하며 이전 등록 버전을 보존합니다. 제거는 등록을 비활성화하고 수집본·이력을 남깁니다. 같은 provider URL의 중복 등록은 같은 인증 참조일 때만 멱등 처리합니다. 참조 변경은 제거 후 명시적으로 다시 등록합니다. 남아 있는 잠금은 `REGISTRY_BUSY`로 반환하며 임의로 지우지 않습니다. 다른 형식의 등록 영역과 심볼릭 링크는 거절합니다.

신원 상태는 `REGISTERED_UNVERIFIED`와 `IDENTITY_VERIFIED`입니다. 검증한 이름 변경은 고정 숫자 ID를 유지하며 ID 변경은 거절합니다. 공개 여부는 미확인으로 남을 수 있습니다. GitLab의 명시적 `empty_repo`는 EMPTY/NONEMPTY를 확정할 수 있지만 GitHub `size=0`은 근거가 부족해 UNKNOWN입니다. 404는 비공개 접근 불가를 포함하는 `ACCESS_UNKNOWN`이며 빈 저장소·삭제로 판정하지 않습니다.

## 인증과 HTTP 계약

- 요청 시작 시에만 지정 환경 변수의 값을 읽습니다. 디스크에는 이름만 저장합니다. CLI·브라우저 응답에는 `credential_configured`만 표시합니다. 토큰 입력 필드·토큰 인수·URL 자격증명·키체인 조회·gh/glab 자동 탐색은 제공하지 않습니다.
- 소유한 요청 subprocess는 stdin 파이프로 토큰을 받고 지정 인증 헤더만 만듭니다. 자식 환경에는 인증 변수와 외부 프록시 설정을 전달하지 않습니다. 자격증명·응답 본문의 디스크 캐시는 만들지 않습니다. provider 헤더·본문에 인증값이 반사되면 캐시·게시 전에 거절합니다.
- 운영 경로는 표준 인증서 검증을 적용한 HTTPS로 `api.github.com` 또는 `gitlab.com/api/v4`만 사용합니다. GitHub API 버전은 `2026-03-10`으로 고정합니다. 임의 fetch origin·TLS 우회 설정은 없습니다. 시험 fixture 주입은 Python 의존성에만 있습니다.
- identity·branch·tag·commit·tree·blob의 지정 GET/HEAD endpoint만 허용합니다. identity 외 요청에는 연결된 저장소 ID가 필요합니다. 임의 GET 프록시·provider 쓰기·계정 전체 탐색·clone/fetch·프로젝트 실행은 추가하지 않습니다.
- redirect·페이지 링크의 origin·endpoint·저장소·고정 ref를 검증합니다. 해당 범위 안의 숫자 ID 신원 redirect와 GitLab tree 페이지만 따라갑니다. 커서 순환·범위 변경·모호한 링크는 명시적으로 실패합니다.
- origin별 공통 요청 게이트, 기본 작업당 300회/120초, I/O 5초, 소유 요청 10초 제한을 사용합니다. 페이지·재시도도 같은 예산을 사용합니다. JSON 응답은 16 MiB, GitLab raw blob은 1 MiB, GitHub 인코딩 blob 응답은 2 MiB로 제한합니다. 원문 복호화·바이트 검증은 H2/H3에서 추가로 수행해야 합니다.
- 대상 transport·5xx 실패만 최대 두 번 재시도합니다. 인증 변수 부재·401·권한 거절 403·사용량 제한·접근 미확인 404를 구분합니다. 재시도·리셋 시각을 반환하며 무제한 백그라운드 재시도를 하지 않습니다. 잘못된/중복 JSON·HTML·과대/잘린 본문을 거절합니다.
- ETag 본문은 한도가 있는 프로세스 메모리에만 두며 reader의 등록·신원·인증 세션별로 격리합니다. 인증값이 바뀌면 해당 구획을 비웁니다. 대응 캐시가 없는 304는 실패합니다. H0의 명시적으로 보존한 snapshot은 별도 과거 근거로 유지합니다.

## 로컬 API와 소유 작업

기존 foreground Local 포털에 아래 경로를 추가하며 loopback Host·Origin·bearer 검사를 유지합니다. 등록·작업 처리는 활성 프로젝트 지도 잠금을 점유하지 않습니다. POST는 자료형이 정해진 JSON, `Content-Type: application/json`, 하나의 Content-Length, 최대 8 KiB를 요구합니다. 토큰 값·임의 fetch URL은 받지 않습니다.

| 방식 | 경로 | 본문 / 결과 |
| --- | --- | --- |
| GET | `/api/registrations` | 활성 등록의 공개 요약 |
| POST | `/api/registrations` | `{provider,url,credential_env?}` → 미확인 등록 요약 |
| POST | `/api/registrations/ID/remove` | `{}` → 비활성 요약 |
| POST | `/api/jobs/probe` | `{source_id}` → 신원 확인 작업 |
| GET | `/api/jobs/ID` | 상태·단계·완료 요청 수·정제한 결과/오류 |
| POST | `/api/jobs/ID/cancel` | `{}` → 취소 요청 접수 |

작업 상태는 QUEUED·RUNNING·CANCEL_REQUESTED·CANCELLED·SUPERSEDED·SUCCEEDED·FAILED입니다. 요청 수는 작업 종료 시 확정합니다. 취소 접수와 정지 상태는 구분하며 terminal까지 조회합니다. 같은 등록의 새 확인은 이전 확인을 대체합니다. 신원 게시 전에 취소·generation·등록 버전을 검사합니다. 실패·취소·늦은 응답은 활성 Local 지도를 변경하지 않습니다. 종료 시 소유 작업·프로세스를 취소/회수하고 임시 클라이언트를 비웁니다. 작업 상태는 메모리에서 한도를 두고 관리하며 CALF 실행 receipt나 영구 작업 큐가 아닙니다.

## 실제 검증과 한계

최종 macOS 저장소 검사 **62개: 기존 22 + H0 12 + H1 28**이 통과했습니다. H1 fixture는 실제 로컬 HTTP subprocess, 인증 헤더 위치, 제한된 redirect·페이지, 인증값 반사·교체, 상태·캐시·예산·본문 실패, 정지 worker, 취소·generation 경쟁, 로컬 API 보호, 취소 중 Local 지도 계속 열기를 검사합니다. 신뢰하지 않는 인증서를 제공하는 실제 로컬 TLS 서버는 거절했습니다. GitLab 한글·플러스 namespace를 한 번만 인코딩하며 잘린 신원 응답을 성공 자료로 사용하지 않습니다.

FFmpeg 계약 검사 3개가 통과했습니다. 새로운 실제 Chrome의 실시간·오프라인 검사에서 지도·코드·Diff·호출 줄·북마크·영·한 전환·핀치 에뮬레이션·1440/390/320 폭이 런타임 오류 없이 통과했습니다. 오프라인 열기 시 원래 fixture 저장소를 숨겼습니다. 서버·수신 소켓·소유 시험 브라우저를 정리했습니다. 새로운 hosted 소스 입력 UI는 추가하거나 검증하지 않았습니다.

H1 시작 때의 **보호 파일 607개** 해시를 보존했습니다. 기존 FFmpeg·라이선스·릴리즈 파일, 과거 v1 자료, 이전 CALF 보존 집합을 포함합니다. 다른 작업의 README·패키지 변경은 그대로입니다. H0 소스에서는 의도한 CLI·포털 연결부만 변경했습니다. native CALF 기록에 쓰지 않았으며 이번 검증에서 커밋·push·실제 provider 요청·소유자 자격증명 조회·원격 변경은 수행하지 않았습니다.

실제 공개/비공개 GitHub·GitLab 접근, 신뢰된 공개 TLS 성공, hosted 수집·지도·Diff·내보내기, H1 Windows·Linux, 새 패키지 설치, 성능·메모리 검증, 실물 스마트폰·외부 에디터 실제 실행은 **NOT_RUN**입니다. 전체 HG01–HG32 판정은 NOT_RUN으로 유지하며 연결한 검증 기록에 H1 fixture 범위의 진행만 추가합니다. 다음은 H2 GitHub 고정 ref/tree/blob reader입니다.

